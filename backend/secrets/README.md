# Firebase Admin SDK keys live here (gitignored)

Place `firebase-admin.json` (downloaded from Firebase Console → Project settings → Service accounts → Generate new private key) in this directory, then set in `backend/.env`:

```
FIREBASE_CREDENTIALS_PATH=./secrets/firebase-admin.json
FIREBASE_PROJECT_ID=your-project-id
```

NEVER commit the JSON. Only this README is tracked. The whole `secrets/` tree is in `.gitignore` except `.gitkeep` and this file.
