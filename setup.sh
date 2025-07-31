#!/bin/bash

# Setup script for AITech application
# This script runs database migrations and initializes the application

echo "🚀 Starting AITech setup..."

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 is not installed"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📚 Installing dependencies..."
pip install -r requirements.txt

# Run database migrations
echo "🗄️ Running database migrations..."
python migration_manager.py migrate

# Initialize database if needed
echo "🔧 Initializing database..."
python -c "from app import init_db; init_db()"

echo "✅ Setup completed successfully!"
echo "🌟 You can now start the application with: python app.py"