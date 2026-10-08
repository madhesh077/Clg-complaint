# College Complaint Management System - GitHub + Render

This package is prepared to deploy the Flask website to Render so it can be opened from any phone or computer using a public HTTPS URL.

## 1. Upload to GitHub
1. Create a new GitHub repository (for example: `college-complaint-management`).
2. Upload ALL files in this folder, including `app.py`, `templates/`, `requirements.txt`, `render.yaml`, and `Procfile`.
3. Do NOT upload `college.db` or student data. It is ignored by `.gitignore`.

## 2. Deploy on Render
1. Sign in to Render and choose **New -> Web Service**.
2. Connect your GitHub repository.
3. Runtime: **Python**.
4. Build Command: `pip install -r requirements.txt`
5. Start Command: `gunicorn app:app`
6. Click **Create Web Service**.
7. Wait for the deployment to become **Live**.
8. Render will give you a public URL similar to `https://college-complaint-management.onrender.com`.

## 3. Admin login
Default admin:
- Username: `admin`
- Password: `admin123`

You can also use the **Admin Register** button on the home page to create another admin account.

## Important: SQLite on Render
The default `college.db` is stored on the service filesystem. On free/ephemeral deployments, database data can be lost when the service is replaced/redeployed. For a real production system, use a managed PostgreSQL database or a Render persistent disk and point `DB_PATH` to that disk.

## Mobile access
Once Render is Live, open the Render HTTPS URL on any mobile phone. The phone does not need to run Python or be on the same Wi-Fi network.
