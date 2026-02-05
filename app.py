from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
import json
import random
import requests
import threading
import time
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = 'sua-chave-secreta'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cardapio.db'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)

WHATSAPP_BOT_URL = "http://localhost:3001"

# Modelos
class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    restaurante_id = db.Column(db.Integer, db.ForeignKey('restaurante.id'), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    senha_hash = db.Column(db.String(255), nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    
    restaurante = db.relationship('Restaurante', backref=db.backref('admins', lazy=True))
    
    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)
    
    def check_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)

class Restaurante(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    descricao = db.Column(db.Text)
    telefone = db.Column(db.String(20))
    
    cor_primaria = db.Column(db.String(7), default='#EA1D2C')
    cor_secundaria = db.Column(db.String(7), default='#F6F6F6')
    cor_fundo = db.Column(db.String(7), default='#FFFFFF')
    
    taxa_entrega = db.Column(db.Float, default=5.00)
    tempo_entrega = db.Column(db.String(50), default='30-45 min')
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    
    categorias = db.relationship('Categoria', backref='restaurante', lazy=True)
    produtos = db.relationship('Produto', backref='restaurante', lazy=True)
    pedidos = db.relationship('Pedido', backref='restaurante', lazy=True)

class Categoria(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    restaurante_id = db.Column(db.Integer, db.ForeignKey('restaurante.id'), nullable=False)
    nome = db.Column(db.String(50), nullable=False)
    posicao = db.Column(db.Integer, default=0)
    ativa = db.Column(db.Boolean, default=True)
    
    produtos = db.relationship('Produto', backref='categoria_obj', lazy=True)

class Produto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    restaurante_id = db.Column(db.Integer, db.ForeignKey('restaurante.id'), nullable=False)
    categoria_id = db.Column(db.Integer, db.ForeignKey('categoria.id'))
    
    nome = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.Text)
    preco = db.Column(db.Float, nullable=False)
    preco_promocional = db.Column(db.Float)
    imagem = db.Column(db.String(200))
    disponivel = db.Column(db.Boolean, default=True)
    destaque = db.Column(db.Boolean, default=False)
    posicao = db.Column(db.Integer, default=0)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

class Pedido(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    restaurante_id = db.Column(db.Integer, db.ForeignKey('restaurante.id'), nullable=False)
    numero_pedido = db.Column(db.String(20), unique=True, nullable=False)
    
    nome_cliente = db.Column(db.String(100), nullable=False)
    telefone = db.Column(db.String(20), nullable=False)
    endereco = db.Column(db.Text, nullable=False)
    observacoes = db.Column(db.Text)
    
    status = db.Column(db.String(20), default='recebido')
    forma_pagamento = db.Column(db.String(20), default='dinheiro')
    valor_total = db.Column(db.Float, nullable=False)
    taxa_entrega = db.Column(db.Float, default=0.0)
    itens_json = db.Column(db.Text, nullable=False)
    
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @property
    def itens(self):
        return json.loads(self.itens_json) if self.itens_json else []
    
    @property
    def status_display(self):
        status_map = {
            'recebido': '📥 Recebido',
            'confirmado': '✅ Confirmado',
            'preparando': '👨‍🍳 Preparando',
            'pronto': '🏃 Pronto',
            'a_caminho': '🚗 A Caminho',
            'entregue': '🎉 Entregue',
            'cancelado': '❌ Cancelado'
        }
        return status_map.get(self.status, self.status)
    
    @property
    def status_cor(self):
        cores = {
            'recebido': '#FFA726',
            'confirmado': '#42A5F5',
            'preparando': '#AB47BC',
            'pronto': '#66BB6A',
            'a_caminho': '#29B6F6',
            'entregue': '#4CAF50',
            'cancelado': '#EF5350'
        }
        return cores.get(self.status, '#9E9E9E')

# WhatsApp Notifier simplificado
class WhatsAppNotifier:
    def __init__(self):
        self.base_url = WHATSAPP_BOT_URL
        self.is_connected = False
        self._check_connection()
    
    def _check_connection(self):
        try:
            response = requests.get(f"{self.base_url}/status", timeout=5)
            if response.status_code == 200:
                self.is_connected = response.json().get('isReady', False)
                print(f"📱 WhatsApp: {'Conectado' if self.is_connected else 'Desconectado'}")
        except Exception as e:
            print(f"❌ Erro WhatsApp: {e}")
            self.is_connected = False
    
    def _send(self, endpoint, data):
        try:
            response = requests.post(f"{self.base_url}/{endpoint}", json=data, timeout=10)
            return response.json().get('success', False)
        except Exception as e:
            print(f"❌ Erro envio: {e}")
            return False
    
    def send_order_confirmation(self, pedido):
        data = {
            'numero_pedido': pedido.numero_pedido,
            'nome_cliente': pedido.nome_cliente,
            'telefone': pedido.telefone,
            'valor_total': float(pedido.valor_total),
            'forma_pagamento': pedido.forma_pagamento,
            'itens': pedido.itens
        }
        return self._send('send/order-confirmation', {'pedido': data})
    
    def send_status_update(self, pedido, novo_status):
        data = {
            'numero_pedido': pedido.numero_pedido,
            'nome_cliente': pedido.nome_cliente,
            'telefone': pedido.telefone,
            'valor_total': float(pedido.valor_total),
            'forma_pagamento': pedido.forma_pagamento,
            'itens': pedido.itens
        }
        return self._send('send/status-update', {'pedido': data, 'novo_status': novo_status})

whatsapp_notifier = WhatsAppNotifier()

# Decorator login_required
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session or 'restaurante_id' not in session:
            flash('Por favor, faça login para acessar esta página.', 'error')
            return redirect(url_for('login'))
        
        if 'restaurante_id' in kwargs:
            if kwargs['restaurante_id'] != session['restaurante_id']:
                flash('Acesso não autorizado.', 'error')
                return redirect(url_for('admin_dashboard', restaurante_id=session['restaurante_id']))
        
        return f(*args, **kwargs)
    return decorated_function

# Funções auxiliares
def gerar_slug(nome):
    slug = nome.lower().replace(' ', '-').replace('--', '-')
    contador = 1
    while Restaurante.query.filter_by(slug=slug).first():
        slug = f"{slug}-{contador}"
        contador += 1
    return slug

def gerar_numero_pedido():
    return f"P{datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(100, 999)}"

def salvar_imagem(file):
    if file and file.filename:
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_filename = f"{timestamp}_{filename}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
        return unique_filename
    return None

def enviar_notificacao_whatsapp(func, *args):
    def wrapper():
        time.sleep(1)
        try:
            func(*args)
        except Exception as e:
            print(f"❌ Erro notificação: {e}")
    threading.Thread(target=wrapper, daemon=True).start()

# Rotas de Login/Logout
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        senha = request.form.get('senha')
        
        admin = Admin.query.filter_by(email=email).first()
        
        if admin and admin.check_senha(senha):
            session['admin_id'] = admin.id
            session['restaurante_id'] = admin.restaurante_id
            session['admin_email'] = admin.email
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('admin_dashboard', restaurante_id=admin.restaurante_id))
        else:
            flash('Email ou senha incorretos.', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Você saiu do sistema.', 'info')
    return redirect(url_for('login'))

# Rotas para criação do admin
@app.route('/criar', methods=['GET', 'POST'])
def criar_restaurante():
    if request.method == 'POST':
        nome = request.form.get('nome')
        telefone = request.form.get('telefone')
        slug = gerar_slug(nome)
        
        restaurante = Restaurante(nome=nome, slug=slug, telefone=telefone)
        db.session.add(restaurante)
        db.session.commit()
        
        # Criar categorias padrão
        for i, nome_cat in enumerate(['Lanches', 'Bebidas', 'Sobremesas', 'Combos']):
            db.session.add(Categoria(restaurante_id=restaurante.id, nome=nome_cat, posicao=i))
        db.session.commit()
        
        flash('Restaurante criado com sucesso! Agora crie sua conta de administrador.', 'success')
        return redirect(url_for('criar_admin', restaurante_id=restaurante.id))
    
    return '''
    <!DOCTYPE html><html><head><title>Criar Cardápio</title>
    <style>body{font-family:Arial;max-width:500px;margin:50px auto;padding:20px;}
    input,button{width:100%;padding:10px;margin:10px 0;}
    button{background:#EA1D2C;color:white;border:none;}</style>
    </head><body><h2>Criar Meu Cardápio Digital</h2>
    <form method="POST"><input type="text" name="nome" placeholder="Nome do restaurante" required>
    <input type="text" name="telefone" placeholder="Telefone (opcional)">
    <button type="submit">Criar Cardápio</button></form></body></html>'''

@app.route('/criar-admin/<int:restaurante_id>', methods=['GET', 'POST'])
def criar_admin(restaurante_id):
    restaurante = Restaurante.query.get_or_404(restaurante_id)
    
    if Admin.query.filter_by(restaurante_id=restaurante_id).first():
        flash('Este restaurante já possui um administrador. Faça login.', 'info')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        senha = request.form.get('senha')
        confirmar_senha = request.form.get('confirmar_senha')
        
        if Admin.query.filter_by(email=email).first():
            flash('Este email já está cadastrado.', 'error')
            return redirect(url_for('criar_admin', restaurante_id=restaurante_id))
        
        if senha != confirmar_senha:
            flash('As senhas não coincidem.', 'error')
            return redirect(url_for('criar_admin', restaurante_id=restaurante_id))
        
        if len(senha) < 6:
            flash('A senha deve ter pelo menos 6 caracteres.', 'error')
            return redirect(url_for('criar_admin', restaurante_id=restaurante_id))
        
        admin = Admin(restaurante_id=restaurante_id, email=email)
        admin.set_senha(senha)
        db.session.add(admin)
        db.session.commit()
        
        flash('Conta de administrador criada com sucesso! Faça login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('criar_admin.html', restaurante=restaurante)

# Rotas Públicas
@app.route('/')
def index():
    return '''
    <!DOCTYPE html>
    <html>
    <head><title>Cardápio Digital</title>
    <style>body{font-family:Arial;text-align:center;padding:50px;}
    .btn{background:#EA1D2C;color:white;padding:15px 30px;text-decoration:none;
    border-radius:8px;display:inline-block;margin:10px;font-size:18px;}</style>
    </head>
    <body><h1>Cardápio Digital</h1>
    <p>Sistema para restaurantes criarem seu próprio cardápio online</p>
    <a href="/criar" class="btn">Criar Meu Cardápio</a></body></html>'''

# Rotas Admin protegidas
@app.route('/admin/<int:restaurante_id>')
@login_required
def admin_dashboard(restaurante_id):
    restaurante = Restaurante.query.get_or_404(restaurante_id)
    total_produtos = Produto.query.filter_by(restaurante_id=restaurante_id).count()
    total_pedidos = Pedido.query.filter_by(restaurante_id=restaurante_id).count()
    pedidos_recentes = Pedido.query.filter_by(restaurante_id=restaurante_id).order_by(Pedido.criado_em.desc()).limit(5).all()
    
    return render_template('admin/dashboard.html',
                         restaurante=restaurante,
                         total_produtos=total_produtos,
                         total_pedidos=total_pedidos,
                         pedidos_recentes=pedidos_recentes,
                         whatsapp_status=whatsapp_notifier.is_connected)

@app.route('/admin/<int:restaurante_id>/produtos')
@login_required
def admin_produtos(restaurante_id):
    restaurante = Restaurante.query.get_or_404(restaurante_id)
    categorias = Categoria.query.filter_by(restaurante_id=restaurante_id).order_by(Categoria.posicao).all()
    produtos = Produto.query.filter_by(restaurante_id=restaurante_id).order_by(Produto.posicao).all()
    
    return render_template('admin/produtos.html',
                         restaurante=restaurante,
                         categorias=categorias,
                         produtos=produtos)

@app.route('/admin/<int:restaurante_id>/produto/novo', methods=['POST'])
@login_required
def novo_produto(restaurante_id):
    produto = Produto(
        restaurante_id=restaurante_id,
        nome=request.form.get('nome'),
        descricao=request.form.get('descricao'),
        preco=float(request.form.get('preco', 0)),
        categoria_id=request.form.get('categoria_id')
    )
    
    if 'imagem' in request.files:
        imagem = salvar_imagem(request.files['imagem'])
        if imagem:
            produto.imagem = imagem
    
    db.session.add(produto)
    db.session.commit()
    flash('Produto adicionado!', 'success')
    return redirect(f'/admin/{restaurante_id}/produtos')

@app.route('/admin/<int:restaurante_id>/produto/<int:produto_id>/editar', methods=['POST'])
@login_required
def editar_produto(restaurante_id, produto_id):
    produto = Produto.query.get_or_404(produto_id)
    
    if produto.restaurante_id != restaurante_id:
        return 'Acesso negado', 403
    
    produto.nome = request.form.get('nome', produto.nome)
    produto.descricao = request.form.get('descricao', produto.descricao)
    produto.preco = float(request.form.get('preco', produto.preco))
    produto.categoria_id = request.form.get('categoria_id')
    produto.disponivel = 'disponivel' in request.form
    produto.destaque = 'destaque' in request.form
    
    if 'imagem' in request.files:
        imagem = salvar_imagem(request.files['imagem'])
        if imagem:
            produto.imagem = imagem
    
    db.session.commit()
    flash('Produto atualizado!', 'success')
    return redirect(f'/admin/{restaurante_id}/produtos')

@app.route('/admin/<int:restaurante_id>/produto/<int:produto_id>/excluir', methods=['POST'])
@login_required
def excluir_produto(restaurante_id, produto_id):
    produto = Produto.query.get_or_404(produto_id)
    
    if produto.restaurante_id != restaurante_id:
        return jsonify({'error': 'Acesso negado'}), 403
    
    db.session.delete(produto)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/admin/<int:restaurante_id>/pedidos')
@login_required
def admin_pedidos(restaurante_id):
    restaurante = Restaurante.query.get_or_404(restaurante_id)
    status_filter = request.args.get('status')
    
    query = Pedido.query.filter_by(restaurante_id=restaurante_id)
    if status_filter:
        query = query.filter_by(status=status_filter)
    pedidos = query.order_by(Pedido.criado_em.desc()).all()
    
    stats = {}
    for status in ['recebido', 'confirmado', 'preparando', 'pronto', 'a_caminho', 'entregue', 'cancelado']:
        stats[status] = Pedido.query.filter_by(restaurante_id=restaurante_id, status=status).count()
    stats['total'] = sum(stats.values())
    
    return render_template('admin/pedidos.html',
                         restaurante=restaurante,
                         pedidos=pedidos,
                         stats=stats,
                         status_filter=status_filter)

@app.route('/admin/<int:restaurante_id>/pedido/<int:pedido_id>/status', methods=['POST'])
@login_required
def atualizar_status_pedido(restaurante_id, pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    
    if pedido.restaurante_id != restaurante_id:
        return jsonify({'error': 'Acesso negado'}), 403
    
    novo_status = request.json.get('status')
    status_anterior = pedido.status
    
    if novo_status in ['recebido', 'confirmado', 'preparando', 'pronto', 'a_caminho', 'entregue', 'cancelado']:
        pedido.status = novo_status
        db.session.commit()
        
        if novo_status != status_anterior:
            enviar_notificacao_whatsapp(whatsapp_notifier.send_status_update, pedido, novo_status)
        
        return jsonify({
            'success': True, 
            'novo_status': pedido.status_display,
            'status_cor': pedido.status_cor
        })
    
    return jsonify({'error': 'Status inválido'}), 400

@app.route('/admin/<int:restaurante_id>/pedido/<int:pedido_id>/atualizar-status', methods=['POST'])
@login_required
def atualizar_status_pedido_form(restaurante_id, pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    
    if pedido.restaurante_id != restaurante_id:
        flash('Acesso negado', 'error')
        return redirect(f'/admin/{restaurante_id}/pedidos')
    
    novo_status = request.form.get('status')
    status_anterior = pedido.status
    
    if novo_status in ['recebido', 'confirmado', 'preparando', 'pronto', 'a_caminho', 'entregue', 'cancelado']:
        pedido.status = novo_status
        db.session.commit()
        
        if novo_status != status_anterior:
            enviar_notificacao_whatsapp(whatsapp_notifier.send_status_update, pedido, novo_status)
            flash(f'Status atualizado para {pedido.status_display} e notificação enviada!', 'success')
        else:
            flash(f'Status já era {pedido.status_display}', 'info')
    
    return redirect(f'/admin/{restaurante_id}/pedidos')

@app.route('/admin/<int:restaurante_id>/pedido/<int:pedido_id>')
@login_required
def detalhes_pedido(restaurante_id, pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    
    if pedido.restaurante_id != restaurante_id:
        return jsonify({'error': 'Acesso negado'}), 403
    
    return jsonify({
        'id': pedido.id,
        'numero_pedido': pedido.numero_pedido,
        'nome_cliente': pedido.nome_cliente,
        'telefone': pedido.telefone,
        'endereco': pedido.endereco,
        'observacoes': pedido.observacoes,
        'status': pedido.status,
        'status_display': pedido.status_display,
        'status_cor': pedido.status_cor,
        'forma_pagamento': pedido.forma_pagamento,
        'valor_total': pedido.valor_total,
        'taxa_entrega': pedido.taxa_entrega,
        'itens': pedido.itens,
        'criado_em': pedido.criado_em.strftime('%d/%m/%Y %H:%M'),
        'atualizado_em': pedido.atualizado_em.strftime('%d/%m/%Y %H:%M')
    })

@app.route('/admin/<int:restaurante_id>/configuracoes', methods=['GET', 'POST'])
@login_required
def admin_configuracoes(restaurante_id):
    restaurante = Restaurante.query.get_or_404(restaurante_id)
    
    if request.method == 'POST':
        restaurante.nome = request.form.get('nome', restaurante.nome)
        restaurante.descricao = request.form.get('descricao', restaurante.descricao)
        restaurante.telefone = request.form.get('telefone', restaurante.telefone)
        
        restaurante.cor_primaria = request.form.get('cor_primaria', restaurante.cor_primaria)
        restaurante.cor_secundaria = request.form.get('cor_secundaria', restaurante.cor_secundaria)
        restaurante.cor_fundo = request.form.get('cor_fundo', restaurante.cor_fundo)
        
        restaurante.taxa_entrega = float(request.form.get('taxa_entrega', restaurante.taxa_entrega))
        restaurante.tempo_entrega = request.form.get('tempo_entrega', restaurante.tempo_entrega)
        
        if request.form.get('nome') != restaurante.nome:
            restaurante.slug = gerar_slug(request.form.get('nome'))
        
        db.session.commit()
        flash('Configurações atualizadas com sucesso!', 'success')
        return redirect(f'/admin/{restaurante_id}/configuracoes')
    
    return render_template('admin/configuracoes.html', restaurante=restaurante)

@app.route('/admin/<int:restaurante_id>/categorias')
@login_required
def admin_categorias(restaurante_id):
    restaurante = Restaurante.query.get_or_404(restaurante_id)
    categorias = Categoria.query.filter_by(restaurante_id=restaurante_id).order_by(Categoria.posicao).all()
    return render_template('admin/categorias.html', restaurante=restaurante, categorias=categorias)

@app.route('/admin/<int:restaurante_id>/categoria/novo', methods=['POST'])
@login_required
def nova_categoria(restaurante_id):
    categoria = Categoria(
        restaurante_id=restaurante_id,
        nome=request.form.get('nome'),
        posicao=request.form.get('posicao', 0),
        ativa='ativa' in request.form
    )
    db.session.add(categoria)
    db.session.commit()
    flash('Categoria adicionada!', 'success')
    return redirect(f'/admin/{restaurante_id}/categorias')

@app.route('/admin/<int:restaurante_id>/categoria/<int:categoria_id>/editar', methods=['POST'])
@login_required
def editar_categoria(restaurante_id, categoria_id):
    categoria = Categoria.query.get_or_404(categoria_id)
    
    if categoria.restaurante_id != restaurante_id:
        return jsonify({'error': 'Acesso negado'}), 403
    
    categoria.nome = request.form.get('nome', categoria.nome)
    categoria.posicao = int(request.form.get('posicao', categoria.posicao))
    categoria.ativa = 'ativa' in request.form
    db.session.commit()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True})
    
    flash('Categoria atualizada!', 'success')
    return redirect(f'/admin/{restaurante_id}/categorias')

@app.route('/admin/<int:restaurante_id>/categoria/<int:categoria_id>/excluir', methods=['POST'])
@login_required
def excluir_categoria(restaurante_id, categoria_id):
    categoria = Categoria.query.get_or_404(categoria_id)
    
    if categoria.restaurante_id != restaurante_id:
        return jsonify({'error': 'Acesso negado'}), 403
    
    if Produto.query.filter_by(categoria_id=categoria_id).count() > 0:
        return jsonify({'error': 'Não é possível excluir categoria com produtos.'}), 400
    
    db.session.delete(categoria)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/admin/<int:restaurante_id>/categorias/reordenar', methods=['POST'])
@login_required
def reordenar_categorias(restaurante_id):
    for item in request.json.get('categorias', []):
        categoria = Categoria.query.get(item['id'])
        if categoria and categoria.restaurante_id == restaurante_id:
            categoria.posicao = item['posicao']
    db.session.commit()
    return jsonify({'success': True})

@app.route('/admin/<int:restaurante_id>/produtos/reordenar', methods=['POST'])
@login_required
def reordenar_produtos(restaurante_id):
    for item in request.json.get('produtos', []):
        produto = Produto.query.get(item['id'])
        if produto and produto.restaurante_id == restaurante_id:
            produto.posicao = item['posicao']
            produto.categoria_id = item.get('categoria_id')
    db.session.commit()
    return jsonify({'success': True})

@app.route('/admin/<int:restaurante_id>/whatsapp-status')
@login_required
def whatsapp_status(restaurante_id):
    restaurante = Restaurante.query.get_or_404(restaurante_id)
    return render_template('admin/whatsapp_status.html',
                         restaurante=restaurante,
                         status=whatsapp_notifier.is_connected,
                         bot_url=WHATSAPP_BOT_URL)

@app.route('/admin/<int:restaurante_id>/test-whatsapp', methods=['POST'])
@login_required
def test_whatsapp(restaurante_id):
    telefone = request.form.get('telefone')
    if not telefone:
        flash('Digite um número de telefone para teste', 'error')
        return redirect(f'/admin/{restaurante_id}/whatsapp-status')
    
    pedido_teste = type('obj', (object,), {
        'numero_pedido': 'TESTE-123',
        'nome_cliente': 'Cliente Teste',
        'telefone': telefone,
        'valor_total': 50.00,
        'forma_pagamento': 'dinheiro',
        'itens': [{'name': 'Produto Teste', 'quantity': 1, 'subtotal': 50.00}]
    })
    
    if whatsapp_notifier.send_order_confirmation(pedido_teste):
        flash(f'Mensagem de teste enviada para {telefone}', 'success')
    else:
        flash(f'Falha ao enviar mensagem para {telefone}', 'error')
    
    return redirect(f'/admin/{restaurante_id}/whatsapp-status')

# Rota Cardápio Público
@app.route('/cardapio/<slug>')
def cardapio_publico(slug):
    restaurante = Restaurante.query.filter_by(slug=slug).first_or_404()
    
    categorias = []
    for categoria in Categoria.query.filter_by(restaurante_id=restaurante.id, ativa=True).order_by(Categoria.posicao).all():
        produtos = Produto.query.filter_by(restaurante_id=restaurante.id, categoria_id=categoria.id, disponivel=True).order_by(Produto.posicao).all()
        if produtos:
            categorias.append({'categoria': categoria, 'produtos': produtos})
    
    produtos_sem_cat = Produto.query.filter_by(restaurante_id=restaurante.id, disponivel=True, categoria_id=None).all()
    if produtos_sem_cat:
        categorias.append({'categoria': {'nome': 'Outros', 'id': None}, 'produtos': produtos_sem_cat})
    
    return render_template('public/cardapio.html', restaurante=restaurante, categorias=categorias)

# API
@app.route('/api/pedido', methods=['POST'])
def criar_pedido():
    try:
        data = request.get_json()
        
        if not data or not data.get('itens'):
            return jsonify({'error': 'Dados inválidos ou carrinho vazio'}), 400
        
        restaurante = Restaurante.query.filter_by(slug=data.get('restaurante_slug')).first()
        if not restaurante:
            return jsonify({'error': 'Restaurante não encontrado'}), 404
        
        total = data.get('total', 0)
        if total == 0:
            total = sum(item.get('subtotal', 0) for item in data.get('itens', [])) + data.get('taxa_entrega', 0)
        
        pedido = Pedido(
            restaurante_id=restaurante.id,
            numero_pedido=gerar_numero_pedido(),
            nome_cliente=data.get('cliente', {}).get('nome', ''),
            telefone=data.get('cliente', {}).get('telefone', ''),
            endereco=data.get('cliente', {}).get('endereco', ''),
            observacoes=data.get('cliente', {}).get('observacoes', ''),
            forma_pagamento=data.get('forma_pagamento', 'dinheiro'),
            valor_total=total,
            taxa_entrega=data.get('taxa_entrega', 0),
            itens_json=json.dumps(data.get('itens', []))
        )
        
        db.session.add(pedido)
        db.session.commit()
        
        enviar_notificacao_whatsapp(whatsapp_notifier.send_order_confirmation, pedido)
        
        return jsonify({
            'success': True,
            'pedido_id': pedido.id,
            'numero_pedido': pedido.numero_pedido,
            'total': pedido.valor_total,
            'taxa_entrega': pedido.taxa_entrega,
            'mensagem': 'Pedido criado com sucesso!'
        })
        
    except Exception as e:
        print(f"❌ Erro ao criar pedido: {str(e)}")
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

# Rotas auxiliares
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/api/test')
def test_api():
    return jsonify({'status': 'API funcionando', 'timestamp': datetime.now().isoformat()})

@app.route('/health/whatsapp')
def health_whatsapp():
    try:
        response = requests.get(f"{WHATSAPP_BOT_URL}/status", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return jsonify({
                'status': 'healthy',
                'whatsapp_connected': data.get('isReady', False),
                'pending_messages': data.get('pendingMessages', 0)
            })
        return jsonify({'status': 'unhealthy', 'error': 'WhatsApp bot not responding'}), 500
    except:
        return jsonify({'status': 'unhealthy', 'error': 'Cannot connect to WhatsApp bot'}), 500

# Templates HTML
@app.route('/template/login')
def template_login():
    return '''
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - Cardápio Digital</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: Arial, sans-serif;
            background: linear-gradient(135deg, #EA1D2C 0%, #FF6B6B 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .login-container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 15px 35px rgba(0, 0, 0, 0.2);
            width: 100%;
            max-width: 400px;
            padding: 40px;
        }
        .logo {
            text-align: center;
            margin-bottom: 30px;
        }
        .logo h1 {
            color: #EA1D2C;
            font-size: 28px;
        }
        .logo p {
            color: #666;
            margin-top: 5px;
        }
        .form-group {
            margin-bottom: 20px;
        }
        .form-group label {
            display: block;
            margin-bottom: 8px;
            color: #333;
            font-weight: bold;
        }
        .form-group input {
            width: 100%;
            padding: 12px 15px;
            border: 2px solid #ddd;
            border-radius: 10px;
            font-size: 16px;
            transition: border-color 0.3s;
        }
        .form-group input:focus {
            outline: none;
            border-color: #EA1D2C;
        }
        .btn-login {
            width: 100%;
            padding: 14px;
            background: #EA1D2C;
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            transition: background 0.3s;
        }
        .btn-login:hover {
            background: #C41624;
        }
        .flash-messages {
            margin-bottom: 20px;
        }
        .alert {
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 10px;
            font-size: 14px;
        }
        .alert-success {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        .alert-error {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        .register-link {
            text-align: center;
            margin-top: 20px;
            color: #666;
        }
        .register-link a {
            color: #EA1D2C;
            text-decoration: none;
            font-weight: bold;
        }
        .register-link a:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="logo">
            <h1>Cardápio Digital</h1>
            <p>Área Administrativa</p>
        </div>
        
        <div class="flash-messages">
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for category, message in messages %}
                        <div class="alert alert-{{ category }}">
                            {{ message }}
                        </div>
                    {% endfor %}
                {% endif %}
            {% endwith %}
        </div>
        
        <form method="POST" action="{{ url_for('login') }}">
            <div class="form-group">
                <label for="email">Email</label>
                <input type="email" id="email" name="email" required>
            </div>
            
            <div class="form-group">
                <label for="senha">Senha</label>
                <input type="password" id="senha" name="senha" required>
            </div>
            
            <button type="submit" class="btn-login">Entrar</button>
        </form>
        
        <div class="register-link">
            <p>É novo aqui? <a href="{{ url_for('criar_restaurante') }}">Crie seu restaurante</a></p>
        </div>
    </div>
</body>
</html>'''

@app.route('/template/criar_admin')
def template_criar_admin():
    return '''
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Criar Administrador - {{ restaurante.nome }}</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: Arial, sans-serif;
            background: #f5f5f5;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .admin-container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
            width: 100%;
            max-width: 500px;
            padding: 40px;
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
        }
        .header h1 {
            color: #EA1D2C;
            font-size: 24px;
            margin-bottom: 10px;
        }
        .header p {
            color: #666;
            font-size: 16px;
        }
        .restaurante-info {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 25px;
            text-align: center;
        }
        .restaurante-info h3 {
            color: #333;
            margin-bottom: 5px;
        }
        .form-group {
            margin-bottom: 20px;
        }
        .form-group label {
            display: block;
            margin-bottom: 8px;
            color: #333;
            font-weight: bold;
        }
        .form-group input {
            width: 100%;
            padding: 12px 15px;
            border: 2px solid #ddd;
            border-radius: 10px;
            font-size: 16px;
            transition: border-color 0.3s;
        }
        .form-group input:focus {
            outline: none;
            border-color: #EA1D2C;
        }
        .password-requirements {
            font-size: 12px;
            color: #666;
            margin-top: 5px;
        }
        .btn-create {
            width: 100%;
            padding: 14px;
            background: #EA1D2C;
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            transition: background 0.3s;
        }
        .btn-create:hover {
            background: #C41624;
        }
        .flash-messages {
            margin-bottom: 20px;
        }
        .alert {
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 10px;
            font-size: 14px;
        }
        .alert-success {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        .alert-error {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        .login-link {
            text-align: center;
            margin-top: 20px;
            color: #666;
        }
        .login-link a {
            color: #EA1D2C;
            text-decoration: none;
            font-weight: bold;
        }
        .login-link a:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <div class="admin-container">
        <div class="header">
            <h1>Configurar Administrador</h1>
            <p>Crie sua conta para acessar o painel administrativo</p>
        </div>
        
        <div class="restaurante-info">
            <h3>{{ restaurante.nome }}</h3>
            <p>URL do cardápio: cardapio-digital.com/cardapio/{{ restaurante.slug }}</p>
        </div>
        
        <div class="flash-messages">
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for category, message in messages %}
                        <div class="alert alert-{{ category }}">
                            {{ message }}
                        </div>
                    {% endfor %}
                {% endif %}
            {% endwith %}
        </div>
        
        <form method="POST" action="{{ url_for('criar_admin', restaurante_id=restaurante.id) }}">
            <div class="form-group">
                <label for="email">Email</label>
                <input type="email" id="email" name="email" required placeholder="seu@email.com">
            </div>
            
            <div class="form-group">
                <label for="senha">Senha</label>
                <input type="password" id="senha" name="senha" required>
                <div class="password-requirements">Mínimo 6 caracteres</div>
            </div>
            
            <div class="form-group">
                <label for="confirmar_senha">Confirmar Senha</label>
                <input type="password" id="confirmar_senha" name="confirmar_senha" required>
            </div>
            
            <button type="submit" class="btn-create">Criar Conta Administrativa</button>
        </form>
        
        <div class="login-link">
            <p>Já tem uma conta? <a href="{{ url_for('login') }}">Faça login</a></p>
        </div>
    </div>
</body>
</html>'''

# Criar diretório templates se não existir
os.makedirs('templates', exist_ok=True)

# Salvar templates em arquivos
with open('templates/login.html', 'w', encoding='utf-8') as f:
    f.write('''<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - Cardápio Digital</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: Arial, sans-serif;
            background: linear-gradient(135deg, #EA1D2C 0%, #FF6B6B 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .login-container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 15px 35px rgba(0, 0, 0, 0.2);
            width: 100%;
            max-width: 400px;
            padding: 40px;
        }
        .logo {
            text-align: center;
            margin-bottom: 30px;
        }
        .logo h1 {
            color: #EA1D2C;
            font-size: 28px;
        }
        .logo p {
            color: #666;
            margin-top: 5px;
        }
        .form-group {
            margin-bottom: 20px;
        }
        .form-group label {
            display: block;
            margin-bottom: 8px;
            color: #333;
            font-weight: bold;
        }
        .form-group input {
            width: 100%;
            padding: 12px 15px;
            border: 2px solid #ddd;
            border-radius: 10px;
            font-size: 16px;
            transition: border-color 0.3s;
        }
        .form-group input:focus {
            outline: none;
            border-color: #EA1D2C;
        }
        .btn-login {
            width: 100%;
            padding: 14px;
            background: #EA1D2C;
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            transition: background 0.3s;
        }
        .btn-login:hover {
            background: #C41624;
        }
        .flash-messages {
            margin-bottom: 20px;
        }
        .alert {
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 10px;
            font-size: 14px;
        }
        .alert-success {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        .alert-error {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        .register-link {
            text-align: center;
            margin-top: 20px;
            color: #666;
        }
        .register-link a {
            color: #EA1D2C;
            text-decoration: none;
            font-weight: bold;
        }
        .register-link a:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="logo">
            <h1>Cardápio Digital</h1>
            <p>Área Administrativa</p>
        </div>
        
        <div class="flash-messages">
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for category, message in messages %}
                        <div class="alert alert-{{ category }}">
                            {{ message }}
                        </div>
                    {% endfor %}
                {% endif %}
            {% endwith %}
        </div>
        
        <form method="POST" action="{{ url_for('login') }}">
            <div class="form-group">
                <label for="email">Email</label>
                <input type="email" id="email" name="email" required>
            </div>
            
            <div class="form-group">
                <label for="senha">Senha</label>
                <input type="password" id="senha" name="senha" required>
            </div>
            
            <button type="submit" class="btn-login">Entrar</button>
        </form>
        
        <div class="register-link">
            <p>É novo aqui? <a href="{{ url_for('criar_restaurante') }}">Crie seu restaurante</a></p>
        </div>
    </div>
</body>
</html>''')

with open('templates/criar_admin.html', 'w', encoding='utf-8') as f:
    f.write('''<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Criar Administrador - {{ restaurante.nome }}</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: Arial, sans-serif;
            background: #f5f5f5;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .admin-container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
            width: 100%;
            max-width: 500px;
            padding: 40px;
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
        }
        .header h1 {
            color: #EA1D2C;
            font-size: 24px;
            margin-bottom: 10px;
        }
        .header p {
            color: #666;
            font-size: 16px;
        }
        .restaurante-info {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 25px;
            text-align: center;
        }
        .restaurante-info h3 {
            color: #333;
            margin-bottom: 5px;
        }
        .form-group {
            margin-bottom: 20px;
        }
        .form-group label {
            display: block;
            margin-bottom: 8px;
            color: #333;
            font-weight: bold;
        }
        .form-group input {
            width: 100%;
            padding: 12px 15px;
            border: 2px solid #ddd;
            border-radius: 10px;
            font-size: 16px;
            transition: border-color 0.3s;
        }
        .form-group input:focus {
            outline: none;
            border-color: #EA1D2C;
        }
        .password-requirements {
            font-size: 12px;
            color: #666;
            margin-top: 5px;
        }
        .btn-create {
            width: 100%;
            padding: 14px;
            background: #EA1D2C;
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            transition: background 0.3s;
        }
        .btn-create:hover {
            background: #C41624;
        }
        .flash-messages {
            margin-bottom: 20px;
        }
        .alert {
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 10px;
            font-size: 14px;
        }
        .alert-success {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        .alert-error {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        .login-link {
            text-align: center;
            margin-top: 20px;
            color: #666;
        }
        .login-link a {
            color: #EA1D2C;
            text-decoration: none;
            font-weight: bold;
        }
        .login-link a:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <div class="admin-container">
        <div class="header">
            <h1>Configurar Administrador</h1>
            <p>Crie sua conta para acessar o painel administrativo</p>
        </div>
        
        <div class="restaurante-info">
            <h3>{{ restaurante.nome }}</h3>
            <p>URL do cardápio: seu-dominio.com/cardapio/{{ restaurante.slug }}</p>
        </div>
        
        <div class="flash-messages">
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for category, message in messages %}
                        <div class="alert alert-{{ category }}">
                            {{ message }}
                        </div>
                    {% endfor %}
                {% endif %}
            {% endwith %}
        </div>
        
        <form method="POST" action="{{ url_for('criar_admin', restaurante_id=restaurante.id) }}">
            <div class="form-group">
                <label for="email">Email</label>
                <input type="email" id="email" name="email" required placeholder="seu@email.com">
            </div>
            
            <div class="form-group">
                <label for="senha">Senha</label>
                <input type="password" id="senha" name="senha" required>
                <div class="password-requirements">Mínimo 6 caracteres</div>
            </div>
            
            <div class="form-group">
                <label for="confirmar_senha">Confirmar Senha</label>
                <input type="password" id="confirmar_senha" name="confirmar_senha" required>
            </div>
            
            <button type="submit" class="btn-create">Criar Conta Administrativa</button>
        </form>
        
        <div class="login-link">
            <p>Já tem uma conta? <a href="{{ url_for('login') }}">Faça login</a></p>
        </div>
    </div>
</body>
</html>''')

# Inicialização
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    
    print("=" * 50)
    print("🍽️  Cardápio Digital Iniciando...")
    print(f"🌐 Flask: http://localhost:5000")
    print(f"🤖 WhatsApp Bot API: {WHATSAPP_BOT_URL}")
    print("=" * 50)
    print("🔐 Sistema de Login implementado")
    print("   • Rotas /admin/* protegidas")
    print("   • Senhas criptografadas com werkzeug")
    print("   • Sessions configuradas")
    print("=" * 50)
    
    app.run(host="0.0.0.0", port=5000)