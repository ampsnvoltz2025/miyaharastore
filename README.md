# Store Application

A Flask-based store application with admin interface, order management, and barcode scanning capabilities.

## Features

- User authentication and authorization
- Product management
- Shopping cart functionality
- Order processing
- Admin dashboard
- Barcode scanning
- Configurable store settings

## Prerequisites

- Python 3.8+
- pip (Python package manager)
- SQLite (for development)
- Virtual environment (recommended)

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd storeapp
   ```

2. Create and activate a virtual environment:
   ```bash
   # On Windows
   python -m venv venv
   .\venv\Scripts\activate
   
   # On Unix or MacOS
   python -m venv venv
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -e .
   ```

## Configuration

1. Create a `.env` file in the project root with the following variables:
   ```
   FLASK_APP=wsgi:app
   FLASK_ENV=production
   SECRET_KEY=your-secret-key-here
   DATABASE_URI=sqlite:///store.db
   ```

2. For production, set appropriate database connection strings and secrets.

## Database Setup

Initialize the database:
```bash
flask db upgrade
storeapp-initdb
```

## Running the Application

### Development
```bash
flask run
```

### Production with Gunicorn
```bash
gunicorn --bind 0.0.0.0:5000 wsgi:app
```

## Deployment

### Using Gunicorn with Nginx (Recommended for Production)

1. Install Nginx and Gunicorn:
   ```bash
   # On Ubuntu/Debian
   sudo apt update
   sudo apt install nginx
   pip install gunicorn
   ```

2. Create a systemd service for Gunicorn:
   ```
   [Unit]
   Description=Gunicorn instance to serve storeapp
   After=network.target

   [Service]
   User=your_username
   Group=www-data
   WorkingDirectory=/path/to/storeapp
   Environment="PATH=/path/to/venv/bin"
   ExecStart=/path/to/venv/bin/gunicorn --workers 3 --bind unix:storeapp.sock -m 007 wsgi:app

   [Install]
   WantedBy=multi-user.target
   ```

3. Configure Nginx:
   ```
   server {
       listen 80;
       server_name your_domain.com;

       location / {
           include proxy_params;
           proxy_pass http://unix:/path/to/storeapp/storeapp.sock;
       }
   }
   ```

4. Enable and start the services:
   ```bash
   sudo systemctl start storeapp
   sudo systemctl enable storeapp
   sudo systemctl restart nginx
   ```

## Security Considerations

- Use strong secret keys
- Enable HTTPS with Let's Encrypt
- Keep dependencies updated
- Use environment variables for sensitive data
- Follow the principle of least privilege for database users

## License

[Your License Here]
