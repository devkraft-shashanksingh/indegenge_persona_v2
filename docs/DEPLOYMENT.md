# Deployment Guide for PharmaPersonaSim

## 🚀 Frontend Deployment (Vercel)

### Option 1: Deploy via Vercel Dashboard (Recommended)

1. **Go to Vercel**: https://vercel.com
2. **Sign in** with your GitHub account
3. **Import Project**: Click "New Project"
4. **Select Repository**: Choose `ishankgp/indegenge_persona`
5. **Configure Project**:
   - Framework Preset: `Vite`
   - Root Directory: `frontend`
   - Build Command: `npm run build`
   - Output Directory: `dist`
6. **Environment Variables**: Add:
   - `VITE_API_URL`: Your backend API URL (e.g., `https://your-backend.herokuapp.com`)
7. **Deploy**: Click "Deploy"

### Option 2: Deploy via Vercel CLI

\`\`\`bash
# Install Vercel CLI
npm i -g vercel

# Navigate to frontend
cd frontend

# Deploy
vercel

# Follow the prompts:
# - Set up and deploy: Yes
# - Which scope: Your account
# - Link to existing project: No
# - Project name: pharmapersonasim-frontend
# - Directory: ./
# - Override settings: No
\`\`\`

## 🖥️ Backend Deployment Options

### Option 1: Railway (Recommended for simplicity)

1. **Go to Railway**: https://railway.app
2. **Sign in** with GitHub
3. **New Project** → **Deploy from GitHub repo**
4. **Select** `ishankgp/indegenge_persona`
5. **Configure**:
   - Root Directory: `backend`
   - Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
6. **Add Environment Variables**:
   - `OPENAI_API_KEY`: Your OpenAI API key
   - `DATABASE_URL`: (Railway will provide PostgreSQL)
7. **Deploy**

### Option 2: Heroku

1. **Create** `backend/Procfile`:
\`\`\`
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
\`\`\`

2. **Create** `backend/runtime.txt`:
\`\`\`
python-3.10.0
\`\`\`

3. **Deploy**:
\`\`\`bash
cd backend
heroku create your-app-name
heroku config:set OPENAI_API_KEY=your_key_here
git push heroku main
\`\`\`

### Option 3: Render

1. **Go to Render**: https://render.com
2. **New** → **Web Service**
3. **Connect** GitHub repository
4. **Configure**:
   - Name: `pharmapersonasim-backend`
   - Root Directory: `backend`
   - Environment: `Python 3`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. **Environment Variables**:
   - `OPENAI_API_KEY`: Your OpenAI API key
   - `DATABASE_URL`: (Use Render PostgreSQL)
6. **Create Web Service**

## 🔧 Post-Deployment Configuration

### Update Frontend API URL

After deploying the backend, update the frontend:

1. **Vercel Dashboard** → Your Project → Settings → Environment Variables
2. Update `VITE_API_URL` with your backend URL
3. Redeploy frontend

### Database Migration

For production databases (PostgreSQL):

\`\`\`python
# Update backend/app/database.py
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./pharma_personas.db")

# For PostgreSQL on Heroku/Railway
if SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql://", 1)
\`\`\`

### CORS Configuration

Update `backend/app/main.py` with your frontend URL:

\`\`\`python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://your-frontend.vercel.app"  # Add your Vercel URL
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
\`\`\`

## 📊 Monitoring

### Frontend (Vercel)
- Analytics: Vercel Dashboard → Analytics
- Logs: Vercel Dashboard → Functions → Logs

### Backend
- **Railway**: Dashboard → Logs
- **Heroku**: `heroku logs --tail`
- **Render**: Dashboard → Logs

## 🔒 Security Checklist

- [ ] Set strong `OPENAI_API_KEY`
- [ ] Use HTTPS for all endpoints
- [ ] Configure CORS properly
- [ ] Set up rate limiting
- [ ] Use environment variables for secrets
- [ ] Enable authentication (if needed)
- [ ] Regular dependency updates

## 🆘 Troubleshooting

### Frontend Issues

**Build fails on Vercel:**
- Check Node version compatibility
- Verify all dependencies are in `package.json`
- Check build logs for specific errors

**API calls failing:**
- Verify `VITE_API_URL` is set correctly
- Check CORS configuration on backend
- Ensure backend is running

### Backend Issues

**Server won't start:**
- Check Python version (3.10+)
- Verify all dependencies installed
- Check environment variables
- Review logs for import errors

**Database connection issues:**
- Verify `DATABASE_URL` format
- Check database credentials
- Ensure database is accessible

**OpenAI API errors:**
- Verify API key is valid
- Check API quota/limits
- Review error messages in logs

## 📞 Support

For deployment issues:
- Vercel: https://vercel.com/support
- Railway: https://railway.app/help
- Heroku: https://devcenter.heroku.com
- Render: https://render.com/docs

## 🎉 Success!

Once deployed:
1. Frontend URL: `https://your-app.vercel.app`
2. Backend URL: `https://your-backend.herokuapp.com`
3. API Docs: `https://your-backend.herokuapp.com/docs`

Remember to:
- Test all features after deployment
- Monitor logs for errors
- Set up error tracking (Sentry, etc.)
- Configure backups for database
