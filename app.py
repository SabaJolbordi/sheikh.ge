from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import base64
from functools import wraps

# Import db and models
from models import db, User, Category, Product, Order, OrderItem, Message, MessageReply, MessageAttachment, VoiceMessage

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sheikh.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size

# Allowed file extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'mp3', 'wav', 'm4a', 'ogg', 'webm'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# Ensure upload folders exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'messages'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'admin_replies'), exist_ok=True)

# Initialize db with app
db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Admin decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Access denied. Admin privileges required.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)

    return decorated_function


# Custom template filters
@app.template_filter('nl2br')
def nl2br_filter(text):
    if not text:
        return text
    return text.replace('\n', '<br>\n')


# Helper function for formatting message time
def format_message_time(dt):
    """Format datetime for display"""
    if not dt:
        return ''

    now = datetime.now()
    diff = now - dt

    if diff.days == 0:
        return dt.strftime('%H:%M')
    elif diff.days == 1:
        return 'გუშინ'
    elif diff.days < 7:
        return dt.strftime('%A')
    else:
        return dt.strftime('%d.%m.%Y')


# ============================================================================
# Main Routes
# ============================================================================

@app.route('/')
def index():
    products = Product.query.limit(8).all()
    categories = Category.query.all()
    return render_template('index.html', products=products, categories=categories)


@app.route('/shop')
def shop():
    page = request.args.get('page', 1, type=int)
    category_id = request.args.get('category', type=int)
    search = request.args.get('search', '')
    sort = request.args.get('sort', 'newest')
    view = request.args.get('view', 'grid')

    query = Product.query

    if search:
        query = query.filter(Product.name.ilike(f'%{search}%') | Product.description.ilike(f'%{search}%'))

    if category_id:
        query = query.filter(Product.category_id == category_id)

    if sort == 'price_low':
        query = query.order_by(Product.price.asc())
    elif sort == 'price_high':
        query = query.order_by(Product.price.desc())
    else:
        query = query.order_by(Product.created_at.desc())

    pagination = query.paginate(page=page, per_page=12, error_out=False)
    products = pagination.items
    categories = Category.query.all()

    return render_template('shop.html', products=products, categories=categories,
                           pagination=pagination, current_view=view)


@app.route('/product/<int:product_id>')
def product(product_id):
    product = Product.query.get_or_404(product_id)
    return render_template('product.html', product=product)


@app.route('/about')
def about():
    return render_template('about.html')


# ============================================================================
# Contact & Message Routes (User)
# ============================================================================

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        subject = request.form.get('subject', 'New Message')
        message_text = request.form.get('message')
        is_urgent = request.form.get('urgent') == 'on'

        # Try to find existing user by email or phone
        user = User.query.filter((User.email == email) | (User.phone == phone)).first()

        # For non-authenticated users, store in session for later
        if not current_user.is_authenticated and not user:
            session['temp_user'] = {
                'name': name,
                'email': email,
                'phone': phone
            }

        # Create message with user_id if found
        message = Message(
            sender_id=user.id if user else (current_user.id if current_user.is_authenticated else None),
            sender_name=name,
            sender_email=email,
            phone=phone,
            subject=subject,
            message=message_text,
            is_urgent=is_urgent
        )
        db.session.add(message)
        db.session.flush()

        # Handle file attachments
        files = request.files.getlist('attachments')
        for file in files:
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                unique_filename = f"{timestamp}_{filename}"

                file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'messages', unique_filename)
                file.save(file_path)

                file_ext = filename.rsplit('.', 1)[1].lower()
                file_type = 'image' if file_ext in ['png', 'jpg', 'jpeg', 'gif', 'webp'] else 'audio'

                attachment = MessageAttachment(
                    message_id=message.id,
                    filename=filename,
                    file_path=f'uploads/messages/{unique_filename}',
                    file_type=file_type,
                    file_size=os.path.getsize(file_path)
                )
                db.session.add(attachment)
                message.has_attachment = True

        # Handle voice message
        voice_data = request.form.get('voice_message')
        if voice_data and voice_data.startswith('data:audio'):
            try:
                if ',' in voice_data:
                    audio_data = base64.b64decode(voice_data.split(',')[1])
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    audio_filename = f"voice_user_{timestamp}.webm"
                    audio_path = os.path.join(app.config['UPLOAD_FOLDER'], 'messages', audio_filename)

                    with open(audio_path, 'wb') as f:
                        f.write(audio_data)

                    voice = VoiceMessage(
                        message_id=message.id,
                        audio_path=f'uploads/messages/{audio_filename}',
                        duration=int(request.form.get('voice_duration', 0))
                    )
                    db.session.add(voice)
                    message.has_attachment = True
            except Exception as e:
                print(f"Error saving voice message: {e}")

        db.session.commit()

        flash('Your message has been sent successfully! We will respond shortly.', 'success')
        return redirect(url_for('contact'))

    return render_template('contact.html')


# ============================================================================
# API Routes for Messages
# ============================================================================

@app.route('/admin/api/message/<int:message_id>')
@admin_required
def api_message(message_id):
    message = Message.query.get_or_404(message_id)

    # Mark as read
    if message.status == 'unread':
        message.status = 'read'
        db.session.commit()

    # Get replies
    replies = []
    for reply in message.replies:
        replies.append({
            'reply_text': reply.reply_text,
            'reply_type': reply.reply_type,
            'voice_reply_path': reply.voice_reply_path,
            'voice_duration': reply.voice_duration,
            'created_at': reply.created_at.strftime('%Y-%m-%d %H:%M')
        })

    # Get attachments
    attachments = []
    for att in message.attachments:
        attachments.append({
            'filename': att.filename,
            'file_path': att.file_path,
            'file_type': att.file_type,
            'file_size': att.file_size
        })

    return jsonify({
        'id': message.id,
        'sender_name': message.sender_name,
        'sender_email': message.sender_email,
        'phone': message.phone,
        'subject': message.subject,
        'message': message.message,
        'is_urgent': message.is_urgent,
        'status': message.status,
        'created_at': message.created_at.strftime('%Y-%m-%d %H:%M'),
        'attachments': attachments,
        'voice_message': {
            'audio_path': message.voice_message.audio_path,
            'duration': message.voice_message.duration
        } if message.voice_message else None,
        'replies': replies
    })


@app.route('/api/user/messages')
def get_user_messages():
    """Get all messages for current user or temp user"""
    if current_user.is_authenticated:
        messages = Message.query.filter_by(sender_id=current_user.id).order_by(Message.created_at.desc()).all()
    else:
        # For non-authenticated users, check session
        temp_user = session.get('temp_user')
        if temp_user:
            # Search by name OR email OR phone
            messages = Message.query.filter(
                (Message.sender_name == temp_user.get('name')) |
                (Message.sender_email == temp_user.get('email')) |
                (Message.phone == temp_user.get('phone'))
            ).order_by(Message.created_at.desc()).all()
        else:
            messages = []

    return jsonify([{
        'id': m.id,
        'subject': m.subject,
        'message': m.message[:100],
        'created_at': m.created_at.strftime('%Y-%m-%d %H:%M'),
        'status': m.status
    } for m in messages])


@app.route('/api/user/message/<int:message_id>')
def get_user_message_detail(message_id):
    """Get full message details for user"""
    message = Message.query.get_or_404(message_id)

    # Check if user owns this message
    if current_user.is_authenticated:
        if message.sender_id != current_user.id and message.sender_email != current_user.email:
            return jsonify({'error': 'Access denied'}), 403
    else:
        # For temp users, check session
        temp_user = session.get('temp_user')
        if not temp_user or temp_user.get('name') != message.sender_name:
            return jsonify({'error': 'Access denied'}), 403

    # Get replies
    replies = []
    for reply in message.replies:
        replies.append({
            'reply_text': reply.reply_text,
            'reply_type': reply.reply_type,
            'voice_reply_path': reply.voice_reply_path,
            'voice_duration': reply.voice_duration,
            'created_at': reply.created_at.strftime('%Y-%m-%d %H:%M')
        })

    # Get attachments
    attachments = []
    for att in message.attachments:
        attachments.append({
            'filename': att.filename,
            'file_path': att.file_path,
            'file_type': att.file_type
        })

    return jsonify({
        'id': message.id,
        'subject': message.subject,
        'message': message.message,
        'created_at': message.created_at.strftime('%Y-%m-%d %H:%M'),
        'attachments': attachments,
        'voice_message': {
            'audio_path': message.voice_message.audio_path,
            'duration': message.voice_message.duration
        } if message.voice_message else None,
        'replies': replies
    })


# ============================================================================
# Admin Message Management Routes
# ============================================================================

@app.route('/admin/messages')
@admin_required
def admin_messages():
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', 'all')

    query = Message.query
    if status != 'all':
        query = query.filter_by(status=status)

    messages = query.order_by(Message.created_at.desc()).paginate(page=page, per_page=20)

    unread_count = Message.query.filter_by(status='unread').count()
    urgent_count = Message.query.filter_by(is_urgent=True, status='unread').count()
    total_count = Message.query.count()

    return render_template('admin/messages.html',
                           messages=messages,
                           unread_count=unread_count,
                           urgent_count=urgent_count,
                           total_count=total_count,
                           current_status=status,
                           unread_messages_count=unread_count)


@app.route('/admin/messages/<int:message_id>')
@admin_required
def view_message(message_id):
    message = Message.query.get_or_404(message_id)

    if message.status == 'unread':
        message.status = 'read'
        db.session.commit()

    return render_template('admin/message_detail.html', message=message)


@app.route('/admin/messages/<int:message_id>/reply-text', methods=['POST'])
@admin_required
def reply_message_text(message_id):
    message = Message.query.get_or_404(message_id)
    reply_text = request.form.get('reply')

    if reply_text:
        reply = MessageReply(
            message_id=message.id,
            admin_id=current_user.id,
            reply_text=reply_text,
            reply_type='text'
        )
        db.session.add(reply)
        message.status = 'replied'
        db.session.commit()

        flash('Text reply sent successfully!', 'success')

    return redirect(url_for('view_message', message_id=message_id))


@app.route('/admin/messages/<int:message_id>/reply-voice', methods=['POST'])
@admin_required
def reply_message_voice(message_id):
    message = Message.query.get_or_404(message_id)

    voice_data = request.form.get('voice_reply')
    if voice_data and voice_data.startswith('data:audio'):
        try:
            if ',' in voice_data:
                audio_data = base64.b64decode(voice_data.split(',')[1])
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                audio_filename = f"reply_admin_{timestamp}_{message_id}.webm"
                audio_path = os.path.join(app.config['UPLOAD_FOLDER'], 'admin_replies', audio_filename)

                with open(audio_path, 'wb') as f:
                    f.write(audio_data)

                reply = MessageReply(
                    message_id=message.id,
                    admin_id=current_user.id,
                    reply_text='',
                    reply_type='voice',
                    voice_reply_path=f'uploads/admin_replies/{audio_filename}',
                    voice_duration=int(request.form.get('voice_duration', 0))
                )
                db.session.add(reply)
                message.status = 'replied'
                db.session.commit()

                flash('Voice reply sent successfully!', 'success')
        except Exception as e:
            print(f"Error saving voice reply: {e}")
            flash('Error sending voice reply', 'error')

    return redirect(url_for('view_message', message_id=message_id))


@app.route('/admin/messages/<int:message_id>/delete', methods=['POST'])
@admin_required
def delete_message(message_id):
    message = Message.query.get_or_404(message_id)

    # Delete attachments from disk
    for attachment in message.attachments:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'messages',
                                 os.path.basename(attachment.file_path))
        if os.path.exists(file_path):
            os.remove(file_path)

    if message.voice_message:
        audio_path = os.path.join(app.config['UPLOAD_FOLDER'], 'messages',
                                  os.path.basename(message.voice_message.audio_path))
        if os.path.exists(audio_path):
            os.remove(audio_path)

    db.session.delete(message)
    db.session.commit()

    flash('Message deleted successfully', 'success')
    return redirect(url_for('admin_messages'))


@app.route('/admin/messages/bulk-action', methods=['POST'])
@admin_required
def bulk_message_action():
    message_ids = request.form.getlist('message_ids')
    action = request.form.get('action')

    if message_ids:
        if action == 'mark_read':
            Message.query.filter(Message.id.in_(message_ids)).update(
                {'status': 'read'}, synchronize_session=False
            )
            flash(f'{len(message_ids)} messages marked as read', 'success')
        elif action == 'delete':
            for msg_id in message_ids:
                message = Message.query.get(msg_id)
                if message:
                    for attachment in message.attachments:
                        file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'messages',
                                                 os.path.basename(attachment.file_path))
                        if os.path.exists(file_path):
                            os.remove(file_path)
                    if message.voice_message:
                        audio_path = os.path.join(app.config['UPLOAD_FOLDER'], 'messages',
                                                  os.path.basename(message.voice_message.audio_path))
                        if os.path.exists(audio_path):
                            os.remove(audio_path)
                    db.session.delete(message)
            flash(f'{len(message_ids)} messages deleted', 'success')

        db.session.commit()

    return redirect(url_for('admin_messages'))


# ============================================================================
# Authentication Routes
# ============================================================================

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        password = request.form.get('password')

        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'error')
            return redirect(url_for('register'))

        user = User(
            name=name,
            email=email,
            phone=phone,
            password=generate_password_hash(password)
        )
        db.session.add(user)
        db.session.commit()

        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            next_page = request.args.get('next')
            flash('Logged in successfully!', 'success')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            flash('Invalid email or password', 'error')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully', 'success')
    return redirect(url_for('index'))


# ============================================================================
# Cart Routes
# ============================================================================

@app.route('/add-to-cart/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    try:
        quantity = int(request.form.get('quantity', 1))
        product = Product.query.get_or_404(product_id)

        if 'cart' not in session:
            session['cart'] = {}

        cart_id = str(product_id)
        if cart_id in session['cart']:
            session['cart'][cart_id]['quantity'] += quantity
        else:
            session['cart'][cart_id] = {
                'name': product.name,
                'price': float(product.price),
                'quantity': quantity,
                'image': product.image
            }

        session.modified = True

        return jsonify({
            'success': True,
            'message': 'Item added to cart!',
            'cart_count': len(session['cart'])
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 400


@app.route('/cart')
def cart():
    cart_items = []
    total = 0

    if 'cart' in session:
        for product_id, item in session['cart'].items():
            subtotal = item['price'] * item['quantity']
            total += subtotal
            cart_items.append({
                'id': product_id,
                'name': item['name'],
                'price': item['price'],
                'quantity': item['quantity'],
                'image': item['image'],
                'subtotal': subtotal
            })

    return render_template('cart.html', cart_items=cart_items, total=total)


@app.route('/update-cart/<int:product_id>', methods=['POST'])
@login_required
def update_cart(product_id):
    quantity = int(request.form.get('quantity', 1))

    if 'cart' in session and str(product_id) in session['cart']:
        if quantity > 0:
            session['cart'][str(product_id)]['quantity'] = quantity
        else:
            del session['cart'][str(product_id)]
        session.modified = True

    return redirect(url_for('cart'))


@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        address = request.form.get('address')
        city = request.form.get('city', '')

        order = Order(
            user_id=current_user.id,
            name=name,
            phone=phone,
            address=address,
            city=city,
            total=float(request.form.get('total', 0))
        )
        db.session.add(order)
        db.session.flush()

        if 'cart' in session:
            for product_id, item in session['cart'].items():
                order_item = OrderItem(
                    order_id=order.id,
                    product_id=int(product_id),
                    quantity=item['quantity'],
                    price=item['price']
                )
                db.session.add(order_item)

        db.session.commit()
        session.pop('cart', None)

        flash('Your order has been received. We will contact you soon.', 'success')
        return redirect(url_for('order_confirmation', order_id=order.id))

    total = 0
    if 'cart' in session:
        for item in session['cart'].values():
            total += item['price'] * item['quantity']

    return render_template('checkout.html', total=total)


@app.route('/order-confirmation/<int:order_id>')
@login_required
def order_confirmation(order_id):
    order = Order.query.get_or_404(order_id)
    if order.user_id != current_user.id and not current_user.is_admin:
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    return render_template('order_confirmation.html', order=order)


# ============================================================================
# Admin Routes
# ============================================================================

@app.route('/admin')
@admin_required
def admin_dashboard():
    total_products = Product.query.count()
    total_categories = Category.query.count()
    total_orders = Order.query.count()
    total_users = User.query.count()
    unread_messages = Message.query.filter_by(status='unread').count()
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(5).all()

    return render_template('admin/dashboard.html',
                           total_products=total_products,
                           total_categories=total_categories,
                           total_orders=total_orders,
                           total_users=total_users,
                           unread_messages=unread_messages,
                           recent_orders=recent_orders,
                           now=datetime.now())


@app.route('/admin/orders')
@admin_required
def admin_orders():
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return render_template('admin/orders.html', orders=orders)


@app.route('/admin/orders/delete/<int:order_id>', methods=['POST'])
@admin_required
def delete_order(order_id):
    order = Order.query.get_or_404(order_id)

    for item in order.items:
        db.session.delete(item)

    db.session.delete(order)
    db.session.commit()
    flash('Order deleted successfully', 'success')
    return redirect(url_for('admin_orders'))


@app.route('/admin/products')
@admin_required
def admin_products():
    products = Product.query.all()
    categories = Category.query.all()
    return render_template('admin/products.html', products=products, categories=categories)


@app.route('/admin/products/add', methods=['POST'])
@admin_required
def add_product():
    name = request.form.get('name')
    description = request.form.get('description')
    price = float(request.form.get('price'))
    category_id = int(request.form.get('category_id'))

    image = request.files.get('image')
    if image and image.filename:
        filename = secure_filename(image.filename)
        image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        image_path = f'uploads/{filename}'
    else:
        image_path = 'uploads/default.jpg'

    product = Product(
        name=name,
        description=description,
        price=price,
        category_id=category_id,
        image=image_path
    )
    db.session.add(product)
    db.session.commit()

    flash('Product added successfully', 'success')
    return redirect(url_for('admin_products'))


@app.route('/admin/products/edit/<int:product_id>', methods=['GET', 'POST'])
@admin_required
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)

    if request.method == 'POST':
        product.name = request.form.get('name')
        product.description = request.form.get('description')
        product.price = float(request.form.get('price'))
        product.category_id = int(request.form.get('category_id'))

        image = request.files.get('image')
        if image and image.filename:
            filename = secure_filename(image.filename)
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            product.image = f'uploads/{filename}'

        db.session.commit()
        flash('Product updated successfully', 'success')
        return redirect(url_for('admin_products'))

    categories = Category.query.all()
    return render_template('admin/edit_product.html', product=product, categories=categories)


@app.route('/admin/products/delete/<int:product_id>', methods=['POST'])
@admin_required
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    db.session.delete(product)
    db.session.commit()
    flash('Product deleted successfully', 'success')
    return redirect(url_for('admin_products'))


@app.route('/admin/categories')
@admin_required
def admin_categories():
    categories = Category.query.all()
    total_products = sum(len(category.products) for category in categories)
    active_categories = sum(1 for category in categories if len(category.products) > 0)
    return render_template('admin/categories.html',
                           categories=categories,
                           total_products=total_products,
                           active_categories=active_categories)


@app.route('/admin/categories/add', methods=['POST'])
@admin_required
def add_category():
    name = request.form.get('name')
    description = request.form.get('description')

    category = Category(name=name, description=description)
    db.session.add(category)
    db.session.commit()

    flash('Category added successfully', 'success')
    return redirect(url_for('admin_categories'))


@app.route('/admin/categories/edit/<int:category_id>', methods=['POST'])
@admin_required
def edit_category(category_id):
    category = Category.query.get_or_404(category_id)
    category.name = request.form.get('name')
    category.description = request.form.get('description')
    db.session.commit()

    flash('Category updated successfully', 'success')
    return redirect(url_for('admin_categories'))


@app.route('/admin/categories/delete/<int:category_id>', methods=['POST'])
@admin_required
def delete_category(category_id):
    category = Category.query.get_or_404(category_id)
    if category.products:
        flash('Cannot delete category with products', 'error')
        return redirect(url_for('admin_categories'))

    db.session.delete(category)
    db.session.commit()
    flash('Category deleted successfully', 'success')
    return redirect(url_for('admin_categories'))


# ============================================================================
# Admin API Routes for Chat System (CORRECTED)
# ============================================================================

@app.route('/admin/api/search-users')
@admin_required
def search_users():
    """Search users by name, email, or phone"""
    search_term = request.args.get('q', '')
    if not search_term or len(search_term) < 2:
        return jsonify([])

    search_pattern = f"%{search_term}%"
    users = User.query.filter(
        (User.name.ilike(search_pattern)) |
        (User.email.ilike(search_pattern)) |
        (User.phone.ilike(search_pattern))
    ).limit(20).all()

    return jsonify([{
        'id': u.id,
        'name': u.name,
        'email': u.email or '',
        'phone': u.phone or ''
    } for u in users])


@app.route('/admin/api/conversations')
@admin_required
def get_all_conversations():
    """Get all conversations for admin panel"""
    # Get all users who have sent messages
    users_with_messages = db.session.query(
        User.id,
        User.name,
        User.email,
        User.phone,
        db.func.max(Message.created_at).label('last_message_time')
    ).join(Message, User.id == Message.sender_id) \
        .group_by(User.id, User.name, User.email, User.phone) \
        .all()

    conversations = {}

    for user_data in users_with_messages:
        user_id, name, email, phone, last_time = user_data

        # Get last message
        last_message = Message.query.filter_by(sender_id=user_id) \
            .order_by(Message.created_at.desc()).first()

        # Count unread messages (messages without admin reply)
        unread_count = Message.query.filter(
            Message.sender_id == user_id,
            Message.status == 'pending'
        ).count()

        conversations[user_id] = {
            'id': user_id,
            'name': name,
            'email': email or '',
            'phone': phone or '',
            'avatar': name[0].upper() if name else 'U',
            'lastMessage': last_message.message[:50] if last_message else '',
            'lastMessageTime': format_message_time(last_time) if last_time else '',
            'unreadCount': unread_count
        }

    return jsonify({'conversations': conversations})


@app.route('/admin/api/user-conversation/<int:user_id>')
@admin_required
def get_user_conversation(user_id):
    """Get all messages and replies for a specific user in unified format"""
    user = User.query.get_or_404(user_id)

    # Get all messages from this user
    user_messages = Message.query.filter(
        Message.sender_id == user_id
    ).order_by(Message.created_at.asc()).all()

    all_communications = []

    for msg in user_messages:
        # Add user's message
        all_communications.append({
            'id': f"msg_{msg.id}",
            'message_id': msg.id,
            'message': msg.message,
            'sender_type': 'user',
            'sender_name': msg.sender_name or user.name,
            'created_at': msg.created_at.isoformat(),
            'is_user_message': True
        })

        # Add admin replies to this message
        for reply in msg.replies:
            all_communications.append({
                'id': f"reply_{reply.id}",
                'message_id': msg.id,
                'reply_id': reply.id,
                'message': reply.reply_text,
                'sender_type': 'admin',
                'sender_name': 'ადმინისტრატორი',
                'created_at': reply.created_at.isoformat(),
                'reply_type': reply.reply_type,
                'voice_reply_path': reply.voice_reply_path if hasattr(reply, 'voice_reply_path') else None,
                'voice_duration': reply.voice_duration if hasattr(reply, 'voice_duration') else None,
                'is_admin_reply': True
            })

    # Sort by creation time
    all_communications.sort(key=lambda x: x['created_at'])

    # Convert to the format expected by frontend
    formatted_messages = []
    for comm in all_communications:
        formatted_messages.append({
            'id': comm['id'],
            'message': comm['message'],
            'sender_type': comm['sender_type'],
            'sender_name': comm['sender_name'],
            'created_at': comm['created_at'],
            'text': comm['message'],
            'is_voice': comm.get('reply_type') == 'voice' if comm.get('reply_type') else False,
            'voice_url': comm.get('voice_reply_path'),
            'voice_duration': comm.get('voice_duration', 0)
        })

    return jsonify({
        'messages': formatted_messages,
        'user_name': user.name,
        'user_email': user.email or '',
        'user_phone': user.phone or ''
    })


@app.route('/admin/api/send-to-user/<int:user_id>', methods=['POST'])
@admin_required
def send_message_to_user(user_id):
    """Send a text message to a user"""
    user = User.query.get_or_404(user_id)
    message_text = request.form.get('message')
    subject = request.form.get('subject', 'პასუხი ადმინისგან')

    if not message_text:
        return jsonify({'error': 'Message is required'}), 400

    # Find the original message if this is a reply to a specific message
    original_message_id = request.form.get('original_message_id')

    if original_message_id:
        original_message = Message.query.get(original_message_id)
        if original_message:
            # This is a reply to an existing message
            reply = MessageReply(
                message_id=original_message.id,
                admin_id=current_user.id,
                reply_text=message_text,
                reply_type='text'
            )
            db.session.add(reply)
            original_message.status = 'replied'
            db.session.commit()

            return jsonify({'success': True, 'message_id': original_message.id})

    # Create a new message thread
    message = Message(
        sender_id=user.id,
        sender_name=user.name,
        sender_email=user.email,
        phone=user.phone,
        subject=subject,
        message=message_text,
        is_urgent=False,
        status='replied'
    )
    db.session.add(message)
    db.session.flush()

    # Add admin reply
    reply = MessageReply(
        message_id=message.id,
        admin_id=current_user.id,
        reply_text=message_text,
        reply_type='text'
    )
    db.session.add(reply)

    db.session.commit()

    return jsonify({'success': True, 'message_id': message.id})


@app.route('/admin/api/send-voice-to-user/<int:user_id>', methods=['POST'])
@admin_required
def send_voice_to_user(user_id):
    """Send a voice message to a user"""
    user = User.query.get_or_404(user_id)
    voice_data = request.form.get('voice_reply')
    voice_duration = request.form.get('voice_duration', 0, type=int)
    original_message_id = request.form.get('original_message_id')

    if not voice_data:
        return jsonify({'error': 'Voice message is required'}), 400

    # Save voice file
    if ',' in voice_data:
        audio_data = base64.b64decode(voice_data.split(',')[1])
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        audio_filename = f"voice_admin_{timestamp}_{user_id}.webm"
        audio_path = os.path.join(app.config['UPLOAD_FOLDER'], 'messages', audio_filename)

        # Ensure directory exists
        os.makedirs(os.path.dirname(audio_path), exist_ok=True)

        with open(audio_path, 'wb') as f:
            f.write(audio_data)

        relative_path = f'uploads/messages/{audio_filename}'
    else:
        return jsonify({'error': 'Invalid voice data format'}), 400

    if original_message_id:
        original_message = Message.query.get(original_message_id)
        if original_message:
            # Add voice reply to existing message
            reply = MessageReply(
                message_id=original_message.id,
                admin_id=current_user.id,
                reply_text='[ხმოვანი შეტყობინება]',
                reply_type='voice',
                voice_reply_path=relative_path,
                voice_duration=voice_duration
            )
            db.session.add(reply)
            original_message.status = 'replied'

            # Add voice record
            voice = VoiceMessage(
                message_id=original_message.id,
                audio_path=relative_path,
                duration=voice_duration
            )
            db.session.add(voice)

            db.session.commit()
            return jsonify({'success': True, 'message_id': original_message.id})

    # Create new message thread
    message = Message(
        sender_id=user.id,
        sender_name=user.name,
        sender_email=user.email,
        phone=user.phone,
        subject='ხმოვანი შეტყობინება',
        message='[ხმოვანი შეტყობინება]',
        is_urgent=False,
        status='replied',
        has_attachment=True
    )
    db.session.add(message)
    db.session.flush()

    # Add voice record
    voice = VoiceMessage(
        message_id=message.id,
        audio_path=relative_path,
        duration=voice_duration
    )
    db.session.add(voice)

    # Add admin reply
    reply = MessageReply(
        message_id=message.id,
        admin_id=current_user.id,
        reply_text='[ხმოვანი შეტყობინება]',
        reply_type='voice',
        voice_reply_path=relative_path,
        voice_duration=voice_duration
    )
    db.session.add(reply)

    db.session.commit()

    return jsonify({'success': True, 'message_id': message.id})


@app.route('/admin/api/conversation/<int:user_id>/mark-read', methods=['POST'])
@admin_required
def mark_conversation_read(user_id):
    """Mark all messages from a user as read"""
    messages = Message.query.filter(
        Message.sender_id == user_id,
        Message.status == 'pending'
    ).all()

    for message in messages:
        message.status = 'read'

    db.session.commit()
    return jsonify({'success': True})


@app.route('/admin/api/conversation/<int:user_id>/delete', methods=['POST'])
@admin_required
def delete_conversation(user_id):
    """Delete entire conversation with a user"""
    messages = Message.query.filter_by(sender_id=user_id).all()

    for message in messages:
        # Delete associated replies
        MessageReply.query.filter_by(message_id=message.id).delete()
        # Delete voice messages
        VoiceMessage.query.filter_by(message_id=message.id).delete()
        # Delete the message
        db.session.delete(message)

    db.session.commit()
    return jsonify({'success': True})


@app.route('/admin/api/typing/<int:user_id>', methods=['POST'])
@admin_required
def set_typing_status(user_id):
    """Set typing status for a user (admin side)"""
    data = request.get_json()
    is_typing = data.get('isTyping', False)

    # Store typing status in session
    if 'typing_users' not in session:
        session['typing_users'] = {}

    session['typing_users'][str(user_id)] = {
        'is_typing': is_typing,
        'timestamp': datetime.now().isoformat()
    }
    session.modified = True

    return jsonify({'success': True})


@app.route('/admin/api/typing/<int:user_id>/status')
@admin_required
def get_typing_status(user_id):
    """Get typing status for a user"""
    typing_users = session.get('typing_users', {})
    status = typing_users.get(str(user_id), {})

    # Check if status is recent (less than 3 seconds old)
    is_typing = False
    if status and 'timestamp' in status:
        try:
            timestamp = datetime.fromisoformat(status['timestamp'])
            if (datetime.now() - timestamp).total_seconds() < 3:
                is_typing = status.get('is_typing', False)
        except:
            pass

    return jsonify({'isTyping': is_typing})


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("✅ Database tables created successfully!")

        admin = User.query.filter_by(email='sheikh@gmail.com').first()
        if not admin:
            admin = User(
                name='Admin',
                email='sheikh@gmail.com',
                phone='1234567890',
                password=generate_password_hash('sheikh111'),
                is_admin=True
            )
            db.session.add(admin)
            db.session.commit()
            print("✅ Admin user created: sheikh@gmail.com / sheikh111")
        else:
            print("✅ Admin user already exists")

        # Create test categories if none exist
        if Category.query.count() == 0:
            categories = [
                Category(name='საათები', description='ლაქშერი საათების კოლექცია'),
                Category(name='სამკაულები', description='ექსკლუზიური სამკაულები'),
                Category(name='ტანსაცმელი', description='პრემიუმ ტანსაცმელი'),
                Category(name='აქსესუარები', description='ელეგანტური აქსესუარები')
            ]
            for cat in categories:
                db.session.add(cat)
            db.session.commit()
            print("✅ Test categories created!")

        # Create test product if none exist
        if Product.query.count() == 0:
            test_product = Product(
                name='Luxury Gold Watch',
                description='Handcrafted luxury timepiece with 18k gold',
                price=2999.99,
                category_id=1,
                image='uploads/default.jpg'
            )
            db.session.add(test_product)
            db.session.commit()
            print("✅ Test product created!")

    print("\n" + "=" * 50)
    print("🚀 Server running at: http://127.0.0.1:5000")
    print("📧 Message system is active!")
    print("🎤 Voice recording feature available!")
    print("👑 Admin login: sheikh@gmail.com / sheikh111")
    print("=" * 50 + "\n")

    if __name__ == '__main__':
        # Render-ისთვის - გამოიყენე ეს კოდი
        port = int(os.environ.get('PORT', 5000))
        app.run(host='0.0.0.0', port=port, debug=False)