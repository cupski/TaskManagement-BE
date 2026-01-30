# Task Management Backend API

## Instruksi Menjalankan Project

### 1. Clone Repository
```bash
git clone https://github.com/cupski/TaskManagement.git
```

### 2. Masuk ke Folder Backend
```bash
cd TaskManagement/task-management-backend
```

### 3. Setup Virtual Environment

#### Jika Menggunakan Windows (venv sudah tersedia)

Langsung aktifkan virtual environment yang sudah ada:
```bash
venv\Scripts\activate
```

#### Jika Menggunakan OS Lain (Linux/macOS) atau venv tidak kompatibel

Buat virtual environment baru:
```bash
python3 -m venv venv
source venv/bin/activate
```

Lalu install dependencies secara manual (karena tidak ada `requirements.txt`):
```bash
pip install fastapi uvicorn python-dotenv sqlalchemy pyjwt passlib python-multipart
```

### 4. Konfigurasi Environment Variable

Salin file `.env.example` menjadi `.env`:
```bash
cp .env.example .env
```

**Windows (jika `cp` tidak tersedia):**
```bash
copy .env.example .env
```

Sesuaikan isi `.env` dengan konfigurasi database dan secret key.

### 5. Jalankan Server
```bash
uvicorn app.main:app --reload
```

---

## Entity Relationship Diagram (ERD)

Untuk  struktur database,  dapat dilihat ERD dengan dua cara:

### 1. Melihat Gambar ERD

Buka file:
```
Task_ERD.png
```

### 2. Menggunakan dbdiagram.io

Salin isi file:
```
Task_ERD_dbdiagram.txt
```

Lalu paste ke [dbdiagram.io](https://dbdiagram.io) untuk melihat ERD secara interaktif.

---

## Struktur Folder
```
task-management-backend/
├─ app/
│  ├─ models/            # Model database
│  ├─ routers/           # Endpoint API (auth, users, tasks)
│  ├─ schemas/           # Pydantic schemas
│  ├─ utils/             # Config, security, dependencies
│  └─ main.py            # Entry point FastAPI
├─ venv/                 # Virtual environment (Windows)
├─ .env                  # Environment variables
├─ .env.example
├─ Task_ERD.png          # Diagram ERD (gambar)
├─ Task_ERD_dbdiagram.txt # Diagram ERD (sintaks dbdiagram)
├─ task-Management-API.postman_collection.json
└─ README.md
```

---

## Testing API

Gunakan file Postman collection:
```
task-Management-API.postman_collection.json
```

---

## Catatan

- Backend menggunakan FastAPI
- Autentikasi menggunakan JWT
- Virtual environment (`venv/`) sudah disertakan untuk pengguna Windows
- Pengguna Linux/macOS perlu membuat virtual environment baru

---
