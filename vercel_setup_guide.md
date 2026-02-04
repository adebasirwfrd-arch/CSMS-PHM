# Vercel Environment Variable Setup Guide

Agar aplikasi tidak crash di Vercel, Anda **WAJIB** memasukkan semua variabel dari file `.env` ke **Vercel Dashboard**.

### Langkah-langkah:
1.  Buka **Vercel Dashboard** -> Pilih Project **CSMS-PHM**.
2.  Pergi ke tab **Settings** -> **Environment Variables**.
3.  Masukkan variabel berikut satu per satu (Copy-Paste dari file `.env` lokal Anda):

| Variable Name | Description |
| :--- | :--- |
| `SUPABASE_URL` | URL Supabase Anda |
| `SUPABASE_KEY` | Service Role/Anon Key Supabase |
| `SERVICE_ACCOUNT_JSON` | Seluruh isi JSON Service Account (Minified) |
| `GOOGLE_DRIVE_FOLDER_ID` | ID Folder Google Drive |
| `BREVO_API_KEY` | API Key dari Brevo |
| `BREVO_SENDER_EMAIL` | Email pengirim Brevo |
| `BREVO_SENDER_NAME` | Nama pengirim (misal: "CSMS PHM") |
| `DEFAULT_REMINDER_EMAIL` | Email default untuk testing/reminder |

### Penting!
- Karena file `.env` di-ignore oleh Git, Vercel tidak bisa membacanya secara otomatis.
- Setelah memasukan semua variabel, Anda mungkin perlu melakukan **Redeploy** (Tab "Deployments" -> Klik titik tiga di deployment terakhir -> "Redeploy").

### Tips Keamanan
- Anda bisa mencentang "Encrypt" atau membiarkannya default (Vercel sudah mengenkripsi rahasia tersebut).
- Pastikan tidak ada spasi di awal atau akhir nilai saat paste.
