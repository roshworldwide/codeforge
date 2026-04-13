#!/bin/bash
# ╔══════════════════════════════════════════════════════════════════╗
# ║  CodeForge — One-Command Setup Script                           ║
# ╚══════════════════════════════════════════════════════════════════╝

set -e

echo "🔥 CodeForge Setup"
echo "═══════════════════════════════════════"

# Step 1: Python virtual environment
echo ""
echo "📦 Setting up Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "   ✅ Virtual environment created"
else
    echo "   ✅ Virtual environment already exists"
fi

source venv/bin/activate

# Step 2: Install dependencies
echo ""
echo "📥 Installing Python dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "   ✅ Dependencies installed"

# Step 3: Generate Prisma client
echo ""
echo "🔧 Generating Prisma client..."
cd prisma
python3 -m prisma generate
echo "   ✅ Prisma client generated"

# Step 4: Run database migrations
echo ""
echo "🗄️  Setting up SQLite database..."
python3 -m prisma db push
echo "   ✅ Database schema applied"
cd ..

# Done
echo ""
echo "═══════════════════════════════════════"
echo "🚀 CodeForge is ready!"
echo ""
echo "Start the server with:"
echo "  source venv/bin/activate"
echo "  python3 -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000"
echo ""
echo "Then open: http://localhost:8000"
echo "═══════════════════════════════════════"
