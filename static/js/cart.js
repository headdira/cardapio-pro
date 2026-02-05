// Carrinho de Compras com Mercado Pago
class ShoppingCart {
    constructor() {
        this.items = JSON.parse(localStorage.getItem('cart')) || [];
        this.restaurantId = document.body.dataset.restaurantId;
        this.restaurantSlug = document.body.dataset.restaurantSlug;
        console.log('🛒 Carrinho inicializado:', this.restaurantSlug);
        this.init();
    }

    init() {
        this.updateCartCount();
        this.bindEvents();
        this.renderCart();
        this.animateOnLoad();
    }

    animateOnLoad() {
        // Animação de entrada dos produtos
        document.querySelectorAll('.product-card').forEach((card, index) => {
            card.style.animationDelay = `${index * 0.05}s`;
        });
    }

    bindEvents() {
        // Botões "Adicionar ao Carrinho"
        document.addEventListener('click', (e) => {
            const addBtn = e.target.closest('.add-to-cart');
            if (addBtn) {
                const productCard = addBtn.closest('.product-card');
                if (productCard) {
                    this.addItem({
                        id: productCard.dataset.id,
                        name: productCard.dataset.name,
                        price: parseFloat(productCard.dataset.price),
                        image: productCard.dataset.image,
                        description: productCard.dataset.description
                    });
                    
                    // Animação do botão
                    this.animateButton(addBtn);
                }
            }
        });

        // Botão do carrinho
        document.querySelector('.cart-btn').addEventListener('click', () => this.openCart());

        // Botão fechar carrinho
        document.querySelector('.close-cart').addEventListener('click', () => this.closeCart());

        // Overlay
        document.querySelector('.overlay').addEventListener('click', () => this.closeAll());

        // Checkout
        document.querySelector('.checkout-btn').addEventListener('click', () => this.openCheckout());

        // Fechar modal
        document.querySelector('.close-modal').addEventListener('click', () => this.closeCheckout());

        // Finalizar pedido
        document.querySelector('.submit-order').addEventListener('click', (e) => this.submitOrder(e));
    }

    animateButton(button) {
        button.style.transform = 'scale(0.9)';
        setTimeout(() => {
            button.style.transform = '';
        }, 200);
    }

    addItem(product) {
        const existingItem = this.items.find(item => item.id === product.id);
        
        if (existingItem) {
            existingItem.quantity += 1;
        } else {
            this.items.push({
                ...product,
                quantity: 1
            });
        }

        this.saveCart();
        this.updateCartCount();
        this.renderCart();
        
        this.showNotification(`${product.name} adicionado ao carrinho!`, 'success');
        this.playSound('add');
    }

    removeItem(productId) {
        const item = this.items.find(item => item.id === productId);
        this.items = this.items.filter(item => item.id !== productId);
        this.saveCart();
        this.updateCartCount();
        this.renderCart();
        
        if (item) {
            this.showNotification(`${item.name} removido do carrinho`, 'error');
        }
        this.playSound('remove');
    }

    updateQuantity(productId, change) {
        const item = this.items.find(item => item.id === productId);
        if (item) {
            item.quantity += change;
            
            if (item.quantity <= 0) {
                this.removeItem(productId);
            } else {
                this.saveCart();
                this.renderCart();
                this.playSound(change > 0 ? 'add' : 'remove');
            }
        }
    }

    saveCart() {
        localStorage.setItem('cart', JSON.stringify(this.items));
    }

    updateCartCount() {
        const totalItems = this.items.reduce((sum, item) => sum + item.quantity, 0);
        const cartCount = document.querySelector('.cart-count');
        if (cartCount) {
            cartCount.textContent = totalItems;
            cartCount.style.display = totalItems > 0 ? 'inline-block' : 'none';
            
            // Animação do contador
            if (totalItems > 0) {
                cartCount.classList.add('pulse');
                setTimeout(() => cartCount.classList.remove('pulse'), 300);
            }
        }
    }

    openCart() {
        document.querySelector('.cart-sidebar').classList.add('open');
        document.querySelector('.overlay').classList.add('show');
        this.playSound('open');
    }

    closeCart() {
        document.querySelector('.cart-sidebar').classList.remove('open');
        document.querySelector('.overlay').classList.remove('show');
        this.playSound('close');
    }

    closeAll() {
        this.closeCart();
        this.closeCheckout();
    }

    openCheckout() {
        if (this.items.length === 0) {
            this.showNotification('Adicione itens ao carrinho primeiro!', 'error');
            return;
        }

        this.closeCart();
        document.querySelector('.checkout-modal').classList.add('show');
        document.querySelector('.overlay').classList.add('show');
        this.renderOrderSummary();
        this.playSound('open');
    }

    closeCheckout() {
        document.querySelector('.checkout-modal').classList.remove('show');
        document.querySelector('.overlay').classList.remove('show');
        this.playSound('close');
    }

    renderCart() {
        const cartItems = document.querySelector('.cart-items');
        if (!cartItems) return;

        if (this.items.length === 0) {
            cartItems.innerHTML = `
                <div class="empty-cart">
                    <div class="empty-icon">
                        <i class="fas fa-shopping-cart"></i>
                    </div>
                    <h4>Carrinho Vazio</h4>
                    <p>Adicione produtos clicando no botão "+"</p>
                    <button class="continue-shopping" onclick="window.cart.closeCart()">
                        Continuar Comprando
                    </button>
                </div>
            `;
            document.querySelector('.cart-footer').style.display = 'none';
            return;
        }

        document.querySelector('.cart-footer').style.display = 'block';
        
        cartItems.innerHTML = this.items.map(item => `
            <div class="cart-item" data-id="${item.id}">
                <div class="cart-item-image">
                    ${item.image ? 
                        `<img src="${item.image}" alt="${item.name}">` : 
                        `<div class="no-image"><i class="fas fa-utensils"></i></div>`}
                </div>
                <div class="cart-item-info">
                    <div class="cart-item-header">
                        <h4>${item.name}</h4>
                        <button class="remove-btn" title="Remover item">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                    ${item.description ? `<p class="cart-item-desc">${item.description}</p>` : ''}
                    <div class="cart-item-footer">
                        <div class="quantity-controls">
                            <button class="qty-btn minus" title="Diminuir quantidade">
                                <i class="fas fa-minus"></i>
                            </button>
                            <span class="qty">${item.quantity}</span>
                            <button class="qty-btn plus" title="Aumentar quantidade">
                                <i class="fas fa-plus"></i>
                            </button>
                        </div>
                        <div class="cart-item-price">
                            <span class="unit-price">R$ ${item.price.toFixed(2)}</span>
                            <span class="total-price">R$ ${(item.price * item.quantity).toFixed(2)}</span>
                        </div>
                    </div>
                </div>
            </div>
        `).join('');

        // Eventos dos botões
        cartItems.querySelectorAll('.minus').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const itemId = e.target.closest('.cart-item').dataset.id;
                this.updateQuantity(itemId, -1);
            });
        });

        cartItems.querySelectorAll('.plus').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const itemId = e.target.closest('.cart-item').dataset.id;
                this.updateQuantity(itemId, 1);
            });
        });

        cartItems.querySelectorAll('.remove-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const itemId = e.target.closest('.cart-item').dataset.id;
                this.removeItem(itemId);
            });
        });

        this.updateCartTotals();
    }

    updateCartTotals() {
        const subtotal = this.items.reduce((sum, item) => sum + (item.price * item.quantity), 0);
        const taxaEntrega = parseFloat(document.querySelector('.delivery-fee').textContent.replace('R$', '').trim()) || 0;
        const total = subtotal + taxaEntrega;

        document.querySelectorAll('.subtotal').forEach(el => {
            el.textContent = `R$ ${subtotal.toFixed(2)}`;
        });
        
        document.querySelectorAll('.total').forEach(el => {
            el.textContent = `R$ ${total.toFixed(2)}`;
        });
    }

    renderOrderSummary() {
        const orderItems = document.querySelector('.order-items');
        const subtotal = this.items.reduce((sum, item) => sum + (item.price * item.quantity), 0);
        const taxaEntrega = parseFloat(document.querySelector('.delivery-fee').textContent.replace('R$', '').trim()) || 0;
        const total = subtotal + taxaEntrega;

        orderItems.innerHTML = this.items.map(item => `
            <div class="order-item">
                <div class="order-item-info">
                    <span class="order-item-name">${item.quantity}x ${item.name}</span>
                    ${item.description ? `<span class="order-item-desc">${item.description}</span>` : ''}
                </div>
                <span class="order-item-price">R$ ${(item.price * item.quantity).toFixed(2)}</span>
            </div>
        `).join('');

        orderItems.innerHTML += `
            <div class="order-totals">
                <div class="total-row">
                    <span>Subtotal</span>
                    <span>R$ ${subtotal.toFixed(2)}</span>
                </div>
                <div class="total-row">
                    <span>Taxa de entrega</span>
                    <span>R$ ${taxaEntrega.toFixed(2)}</span>
                </div>
                <div class="total-row final">
                    <span>Total</span>
                    <span class="final-total">R$ ${total.toFixed(2)}</span>
                </div>
            </div>
        `;
    }

    async submitOrder(e) {
        e.preventDefault();
        
        // Coletar dados do formulário
        const formData = {
            name: document.getElementById('name').value.trim(),
            address: document.getElementById('address').value.trim(),
            phone: document.getElementById('phone').value.trim(),
            notes: document.getElementById('notes').value.trim()
        };

        // Validação
        if (!formData.name || !formData.address || !formData.phone) {
            this.showNotification('Preencha todos os campos obrigatórios!', 'error');
            this.shakeForm();
            return;
        }

        // Validação de telefone
        const phoneRegex = /^(\d{10,11}|\d{2}\s?\d{8,9})$/;
        if (!phoneRegex.test(formData.phone.replace(/\D/g, ''))) {
            this.showNotification('Digite um telefone válido!', 'error');
            document.getElementById('phone').focus();
            return;
        }

        // Método de pagamento
        const paymentMethod = document.querySelector('.payment-method.selected')?.dataset.method || 'dinheiro';
        
        // Calcular totais
        const subtotal = this.items.reduce((sum, item) => sum + (item.price * item.quantity), 0);
        const taxaEntrega = parseFloat(document.querySelector('.delivery-fee').textContent.replace('R$', '').trim()) || 0;
        const total = subtotal + taxaEntrega;

        // Montar objeto do pedido
        const orderData = {
            restaurante_slug: this.restaurantSlug,
            cliente: {
                nome: formData.name,
                endereco: formData.address,
                telefone: formData.phone,
                observacoes: formData.notes
            },
            forma_pagamento: paymentMethod,
            taxa_entrega: taxaEntrega,
            total: total,
            itens: this.items.map(item => ({
                id: parseInt(item.id),
                name: item.name,
                description: item.description,
                quantity: item.quantity,
                price: item.price,
                subtotal: item.price * item.quantity
            }))
        };

        console.log('Enviando pedido:', orderData);

        // Mostrar loading
        const submitBtn = document.querySelector('.submit-order');
        const originalText = submitBtn.innerHTML;
        submitBtn.innerHTML = '<span class="loading-spinner"></span> Processando...';
        submitBtn.disabled = true;

        try {
            const response = await fetch('/api/pedido', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(orderData)
            });

            const result = await response.json();
            console.log('Resposta:', result);

            if (result.success) {
                // Se for Mercado Pago, processar pagamento
                if (paymentMethod === 'mercadopago') {
                    await this.processarMercadoPago(result.pedido_id);
                } else {
                    // Pagamento em dinheiro - fluxo normal
                    this.showNotification('🎉 Pedido realizado com sucesso!', 'success');
                    this.playSound('success');
                    
                    // Limpar carrinho
                    this.items = [];
                    this.saveCart();
                    this.updateCartCount();
                    
                    // Fechar modais
                    this.closeCheckout();
                    this.closeCart();
                    
                    // Mostrar recibo animado
                    this.showReceipt(result);
                }
            } else {
                this.showNotification(result.error || '❌ Erro ao processar pedido', 'error');
                this.playSound('error');
            }
        } catch (error) {
            console.error('Erro:', error);
            this.showNotification('❌ Erro de conexão', 'error');
            this.playSound('error');
        } finally {
            submitBtn.innerHTML = originalText;
            submitBtn.disabled = false;
        }
    }

    // MÉTODO PARA PROCESSAR MERCADO PAGO
    async processarMercadoPago(pedidoId) {
        try {
            this.showNotification('🔄 Criando pagamento...', 'success');
            
            // Criar pagamento no Mercado Pago
            const response = await fetch(`/api/pagamento/criar/${pedidoId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            const result = await response.json();
            
            if (result.success) {
                if (result.ja_pago) {
                    this.showNotification('✅ Pedido já foi pago!', 'success');
                    // Limpar carrinho
                    this.items = [];
                    this.saveCart();
                    this.updateCartCount();
                    this.closeCheckout();
                    this.closeCart();
                    return;
                }
                
                // Redirecionar para o checkout do Mercado Pago
                this.showNotification('🌐 Redirecionando para pagamento seguro...', 'success');
                
                setTimeout(() => {
                    if (result.init_point) {
                        window.location.href = result.init_point;
                    } else {
                        this.showNotification('❌ Erro ao obter link de pagamento', 'error');
                    }
                }, 1500);
                
            } else {
                this.showNotification(result.error || '❌ Erro ao criar pagamento', 'error');
            }
        } catch (error) {
            console.error('Erro Mercado Pago:', error);
            this.showNotification('❌ Erro no processamento de pagamento', 'error');
        }
    }

    showReceipt(orderData) {
        const overlay = document.createElement('div');
        overlay.className = 'receipt-overlay';
        overlay.innerHTML = `
            <div class="receipt-modal">
                <div class="receipt-header">
                    <div class="receipt-icon">
                        <i class="fas fa-check-circle"></i>
                    </div>
                    <h2>Pedido Confirmado!</h2>
                    <p>Seu pedido foi recebido com sucesso</p>
                </div>
                <div class="receipt-body">
                    <div class="receipt-number">
                        <i class="fas fa-receipt"></i>
                        <div>
                            <small>Número do Pedido</small>
                            <strong>${orderData.numero_pedido}</strong>
                        </div>
                    </div>
                    
                    <div class="receipt-info">
                        <div class="info-item">
                            <i class="fas fa-clock"></i>
                            <div>
                                <small>Tempo Estimado</small>
                                <span>30-45 min</span>
                            </div>
                        </div>
                        <div class="info-item">
                            <i class="fas fa-wallet"></i>
                            <div>
                                <small>Valor Total</small>
                                <span>R$ ${orderData.total}</span>
                            </div>
                        </div>
                    </div>
                    
                    <div class="receipt-message">
                        <p>O restaurante já foi notificado e iniciará o preparo.</p>
                        <p>Você receberá atualizações por WhatsApp!</p>
                    </div>
                </div>
                <button class="close-receipt">
                    <i class="fas fa-check"></i> OK, Entendi!
                </button>
            </div>
        `;

        document.body.appendChild(overlay);

        // Animar entrada
        setTimeout(() => {
            overlay.classList.add('show');
        }, 10);

        overlay.querySelector('.close-receipt').addEventListener('click', () => {
            overlay.classList.remove('show');
            setTimeout(() => overlay.remove(), 300);
            this.playSound('close');
        });
    }

    showNotification(message, type = 'success') {
        // Remover notificações antigas
        document.querySelectorAll('.notification').forEach(n => n.remove());

        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        
        let icon = 'fas fa-check-circle';
        if (type === 'error') icon = 'fas fa-exclamation-circle';
        if (type === 'warning') icon = 'fas fa-exclamation-triangle';
        
        notification.innerHTML = `
            <div class="notification-icon">
                <i class="${icon}"></i>
            </div>
            <div class="notification-content">
                <p>${message}</p>
            </div>
        `;

        document.body.appendChild(notification);

        // Auto-remover após 3 segundos
        setTimeout(() => {
            notification.classList.add('hide');
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }

    playSound(type) {
        try {
            const audioContext = new (window.AudioContext || window.webkitAudioContext)();
            
            let frequency = 440;
            let duration = 0.1;
            
            switch(type) {
                case 'add':
                    frequency = 523.25;
                    break;
                case 'remove':
                    frequency = 392.00;
                    break;
                case 'success':
                    frequency = 659.25;
                    duration = 0.3;
                    break;
                case 'error':
                    frequency = 349.23;
                    break;
                case 'open':
                case 'close':
                    frequency = 493.88;
                    break;
            }
            
            const oscillator = audioContext.createOscillator();
            const gainNode = audioContext.createGain();
            
            oscillator.connect(gainNode);
            gainNode.connect(audioContext.destination);
            
            oscillator.frequency.value = frequency;
            oscillator.type = 'sine';
            
            gainNode.gain.setValueAtTime(0.1, audioContext.currentTime);
            gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + duration);
            
            oscillator.start(audioContext.currentTime);
            oscillator.stop(audioContext.currentTime + duration);
        } catch (e) {
            console.log('Audio não suportado');
        }
    }

    shakeForm() {
        const form = document.querySelector('.checkout-form');
        form.classList.add('shake');
        setTimeout(() => form.classList.remove('shake'), 500);
    }
}

// Inicializar
document.addEventListener('DOMContentLoaded', () => {
    window.cart = new ShoppingCart();
    
    // Adicionar estilos dinâmicos
    const style = document.createElement('style');
    style.textContent = `
        .cart-count.pulse {
            animation: pulse 0.3s ease;
        }
        
        @keyframes pulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.2); }
            100% { transform: scale(1); }
        }
        
        .shake {
            animation: shake 0.5s ease;
        }
        
        @keyframes shake {
            0%, 100% { transform: translateX(0); }
            10%, 30%, 50%, 70%, 90% { transform: translateX(-5px); }
            20%, 40%, 60%, 80% { transform: translateX(5px); }
        }
        
        .notification.hide {
            opacity: 0;
            transform: translateX(100%);
        }
        
        .receipt-overlay {
            opacity: 0;
            transition: opacity 0.3s ease;
        }
        
        .receipt-overlay.show {
            opacity: 1;
        }
        
        .loading-spinner {
            width: 20px;
            height: 20px;
            border: 3px solid rgba(255,255,255,0.3);
            border-radius: 50%;
            border-top-color: white;
            animation: spin 1s linear infinite;
            display: inline-block;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
    `;
    document.head.appendChild(style);
});