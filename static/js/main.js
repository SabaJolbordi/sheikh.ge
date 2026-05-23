// ==========================================================================
// Sheikh.ge - Main JavaScript
// ==========================================================================

document.addEventListener('DOMContentLoaded', function() {
    initHeader();
    initBackToTop();
    initNewsletter();
    initFlashMessages();
    initSlider();
    initImageGallery();
    initQuantityButtons();
});

// ==========================================================================
// Form validation for contact form
// ==========================================================================

function validateContactForm() {
    const name = document.getElementById('name')?.value;
    const email = document.getElementById('email')?.value;
    const message = document.getElementById('message')?.value;

    if (!name || !email || !message) {
        alert('Please fill in all required fields');
        return false;
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
        alert('Please enter a valid email address');
        return false;
    }

    return true;
}

// ==========================================================================
// Search functionality
// ==========================================================================

function searchProducts() {
    const searchTerm = document.getElementById('searchInput')?.value.toLowerCase();
    if (!searchTerm) return;

    const products = document.querySelectorAll('.product-card');
    products.forEach(product => {
        const title = product.querySelector('h3')?.textContent.toLowerCase() || '';
        const description = product.querySelector('.product-description')?.textContent.toLowerCase() || '';

        if (title.includes(searchTerm) || description.includes(searchTerm)) {
            product.style.display = 'block';
        } else {
            product.style.display = 'none';
        }
    });
}

// ==========================================================================
// Price filter
// ==========================================================================

function filterByPrice(min, max) {
    const products = document.querySelectorAll('.product-card');
    products.forEach(product => {
        const priceText = product.querySelector('.product-price')?.textContent || '0';
        const price = parseFloat(priceText.replace('$', '').replace('₾', ''));

        if (price >= min && price <= max) {
            product.style.display = 'block';
        } else {
            product.style.display = 'none';
        }
    });
}

// ==========================================================================
// Sort products
// ==========================================================================

function sortProducts(sortBy) {
    const productsGrid = document.querySelector('.products-grid');
    if (!productsGrid) return;

    const products = Array.from(productsGrid.children);

    products.sort((a, b) => {
        if (sortBy === 'price-low') {
            const priceA = parseFloat(a.querySelector('.product-price')?.textContent.replace('$', '').replace('₾', '') || 0);
            const priceB = parseFloat(b.querySelector('.product-price')?.textContent.replace('$', '').replace('₾', '') || 0);
            return priceA - priceB;
        } else if (sortBy === 'price-high') {
            const priceA = parseFloat(a.querySelector('.product-price')?.textContent.replace('$', '').replace('₾', '') || 0);
            const priceB = parseFloat(b.querySelector('.product-price')?.textContent.replace('$', '').replace('₾', '') || 0);
            return priceB - priceA;
        } else if (sortBy === 'name') {
            const nameA = a.querySelector('h3')?.textContent || '';
            const nameB = b.querySelector('h3')?.textContent || '';
            return nameA.localeCompare(nameB);
        }
        return 0;
    });

    products.forEach(product => productsGrid.appendChild(product));
}

// ==========================================================================
// Add to cart animation
// ==========================================================================

function animateAddToCart(button) {
    const originalText = button.textContent;
    button.textContent = '✓ Added!';
    button.style.background = '#28a745';

    setTimeout(() => {
        button.textContent = originalText;
        button.style.background = '';
    }, 2000);
}

// ==========================================================================
// Quantity selector
// ==========================================================================

function incrementQuantity(inputId) {
    const input = document.getElementById(inputId);
    if (input) {
        input.value = parseInt(input.value) + 1;
    }
}

function decrementQuantity(inputId) {
    const input = document.getElementById(inputId);
    if (input && input.value > 1) {
        input.value = parseInt(input.value) - 1;
    }
}

function initQuantityButtons() {
    const quantitySelectors = document.querySelectorAll('.quantity-selector');
    quantitySelectors.forEach(selector => {
        const input = selector.querySelector('input[type="number"]');
        if (input) {
            const inputId = input.id || 'quantity-' + Math.random();
            input.id = inputId;

            const decrementBtn = document.createElement('button');
            decrementBtn.type = 'button';
            decrementBtn.textContent = '-';
            decrementBtn.className = 'quantity-btn';
            decrementBtn.onclick = () => decrementQuantity(inputId);

            const incrementBtn = document.createElement('button');
            incrementBtn.type = 'button';
            incrementBtn.textContent = '+';
            incrementBtn.className = 'quantity-btn';
            incrementBtn.onclick = () => incrementQuantity(inputId);

            selector.insertBefore(decrementBtn, input);
            selector.appendChild(incrementBtn);
        }
    });
}

// ==========================================================================
// Image gallery for product page
// ==========================================================================

function initImageGallery() {
    const mainImage = document.querySelector('.main-image');
    const thumbnails = document.querySelectorAll('.thumbnail');

    if (thumbnails.length && mainImage) {
        thumbnails.forEach(thumb => {
            thumb.addEventListener('click', function() {
                mainImage.src = this.src;
                thumbnails.forEach(t => t.classList.remove('active'));
                this.classList.add('active');
            });
        });
    }
}

// ==========================================================================
// Wishlist functionality
// ==========================================================================

function toggleWishlist(productId, button) {
    fetch(`/wishlist/toggle/${productId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.in_wishlist) {
            button.classList.add('in-wishlist');
            button.innerHTML = '♥ In Wishlist';
        } else {
            button.classList.remove('in-wishlist');
            button.innerHTML = '♡ Add to Wishlist';
        }
    })
    .catch(error => console.error('Error:', error));
}

// ==========================================================================
// Load more products (pagination)
// ==========================================================================

function loadMore(page) {
    fetch(`/shop/page/${page}`)
        .then(response => response.text())
        .then(html => {
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            const newProducts = doc.querySelector('.products-grid')?.innerHTML;
            if (newProducts) {
                document.querySelector('.products-grid')?.insertAdjacentHTML('beforeend', newProducts);
            }
        })
        .catch(error => console.error('Error loading more products:', error));
}

// ==========================================================================
// Header Functions
// ==========================================================================

function initHeader() {
    const header = document.querySelector('.header');
    const searchToggle = document.getElementById('searchToggle');
    const searchOverlay = document.getElementById('searchOverlay');
    const searchClose = document.getElementById('searchClose');

    // Header scroll effect
    window.addEventListener('scroll', () => {
        if (window.scrollY > 50) {
            header?.classList.add('scrolled');
        } else {
            header?.classList.remove('scrolled');
        }
    });

    // Search toggle
    if (searchToggle && searchOverlay) {
        searchToggle.addEventListener('click', () => {
            searchOverlay.classList.toggle('active');
            if (searchOverlay.classList.contains('active')) {
                searchOverlay.querySelector('input')?.focus();
            }
        });
    }

    // Search close
    if (searchClose && searchOverlay) {
        searchClose.addEventListener('click', () => {
            searchOverlay.classList.remove('active');
        });
    }

    // Close search on escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && searchOverlay?.classList.contains('active')) {
            searchOverlay.classList.remove('active');
        }
    });
}

// ==========================================================================
// Back to Top Button
// ==========================================================================

function initBackToTop() {
    const backToTop = document.getElementById('backToTop');
    if (backToTop) {
        backToTop.addEventListener('click', () => {
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
    }
}

// ==========================================================================
// Newsletter Function
// ==========================================================================

function initNewsletter() {
    const newsletterForm = document.getElementById('newsletterForm');
    if (newsletterForm) {
        newsletterForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const email = this.querySelector('input[type="email"]')?.value;
            if (email) {
                alert('Thank you for subscribing!');
                this.reset();
            }
        });
    }
}

// ==========================================================================
// Flash Messages
// ==========================================================================

function initFlashMessages() {
    const flashMessages = document.querySelectorAll('.flash-message');
    flashMessages.forEach(flash => {
        setTimeout(() => {
            flash.style.opacity = '0';
            setTimeout(() => flash.remove(), 300);
        }, 5000);
    });
}

// ==========================================================================
// Hero Slider
// ==========================================================================

function initSlider() {
    const slides = document.querySelectorAll('.hero-slide');
    const prevBtn = document.querySelector('.slider-control.prev');
    const nextBtn = document.querySelector('.slider-control.next');
    const dots = document.querySelectorAll('.dot');

    if (!slides.length) return;

    let currentSlide = 0;
    let slideInterval;

    function showSlide(index) {
        if (index < 0) index = slides.length - 1;
        if (index >= slides.length) index = 0;

        slides.forEach(slide => slide.classList.remove('active'));
        dots?.forEach(dot => dot.classList.remove('active'));

        slides[index].classList.add('active');
        dots?.[index]?.classList.add('active');
        currentSlide = index;
    }

    function nextSlide() {
        showSlide(currentSlide + 1);
    }

    function prevSlide() {
        showSlide(currentSlide - 1);
    }

    if (prevBtn) prevBtn.addEventListener('click', prevSlide);
    if (nextBtn) nextBtn.addEventListener('click', nextSlide);

    dots?.forEach((dot, index) => {
        dot.addEventListener('click', () => showSlide(index));
    });

    function startSlideShow() {
        slideInterval = setInterval(nextSlide, 5000);
    }

    function stopSlideShow() {
        clearInterval(slideInterval);
    }

    startSlideShow();

    const slider = document.querySelector('.hero-slider');
    if (slider) {
        slider.addEventListener('mouseenter', stopSlideShow);
        slider.addEventListener('mouseleave', startSlideShow);
    }

    showSlide(0);
}
function searchUsers() {
    const searchTerm = document.getElementById('userSearchInput').value.trim();
    console.log('Searching for:', searchTerm);

    if (!searchTerm || searchTerm.length < 2) {
        document.getElementById('searchResults').innerHTML = '';
        return;
    }

    fetch(`/admin/api/search-users?q=${encodeURIComponent(searchTerm)}`)
        .then(response => response.json())
        .then(users => {
            const resultsDiv = document.getElementById('searchResults');
            if (!resultsDiv) return;

            if (users.length === 0) {
                resultsDiv.innerHTML = '<div class="no-results"><i class="fas fa-user-slash"></i> მომხმარებელი ვერ მოიძებნა</div>';
                return;
            }

            resultsDiv.innerHTML = users.map(user => `
                <div class="search-result-item">
                    <div class="search-result-info">
                        <div class="search-result-name">
                            <i class="fas fa-user-circle"></i> ${escapeHtml(user.name)}
                        </div>
                        <div class="search-result-contact">
                            ${user.email ? `<span><i class="fas fa-envelope"></i> ${escapeHtml(user.email)}</span>` : ''}
                            ${user.phone ? `<span><i class="fas fa-phone"></i> ${escapeHtml(user.phone)}</span>` : ''}
                        </div>
                    </div>
                    <button class="search-result-start" onclick="startChatWithUser(${user.id}, '${escapeHtml(user.name)}', '${escapeHtml(user.email || '')}')">
                        <i class="fas fa-comment"></i> ჩატი
                    </button>
                </div>
            `).join('');
        })
        .catch(error => {
            console.error('Error searching users:', error);
            const resultsDiv = document.getElementById('searchResults');
            if (resultsDiv) {
                resultsDiv.innerHTML = '<div class="no-results"><i class="fas fa-exclamation-triangle"></i> შეცდომა ძებნისას</div>';
            }
        });
}