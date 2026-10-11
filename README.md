# 🎙️ Speech-to-Text Dictation Service (Windows)
### מערכת הכתבה קולית מקומית בזמן אמת עם תמיכה מתקדמת בעברית ובאנגלית

מערכת הכתבה שולחנית מקומית (Offline/Local) בעלת שיהוי אפסי (Ultra-Low Latency), הפועלת ברקע של Windows בלחיצה ממושכת על **Right Alt / Fn / Apps** (Push-to-Talk) או במצב דיבור חופשי ("תק-תק").  
המערכת משלבת את מודל **Faster-Whisper** בהאצת חומרה מלאה על כרטיסי מסך NVIDIA RTX (CUDA FP16), כוללת **Control Center Studio** גרפי מלא, מציגה **Dynamic Island HUD** אלגנטי וצף בראש המסך (באיזור הוובקאם), ומזריקה את הטקסט ישירות לחלון הפעיל תוך שמירה מוחלטת על חלון היעד גם אם עברת לחלון אחר תוך כדי דיבור!

---

## ✨ תכונות עיקריות (Key Features)

1. **מרכז בקרה שולחני מלא (Control Center Studio GUI):**
   - חלון שליטה מעוצב (Dark Theme Glassmorphic) הנפתח מיד בהרצת התוכנה.
   - **ניטור מקשים חי (Live Hotkey Monitor):** מציג בדיוק איזה מקש נלחץ בזמן אמת (כולל קוד VK) ומאשר מיידית שהמקש נקלט.
   - **מד עוצמת שמע חי (Live Audio Meter):** visualizer מגיב בזמן אמת לקולך ומאשר שהמיקרופון מחובר וקולט.
   - **אזור בדיקת הכתבה חי (Sandbox):** מאפשר לבדוק את ההכתבה, להחזיק Right Alt ולראות את הטקסט נכתב ישירות בחלון.
   - **שליטה מהירה:** החלפת מודל Whisper, בחירת מיקרופון, הפעלה/כיבוי של צלילי חיווי, נעילת לחיצה כפולה ושחזור חלונות.
   - כפתור "מזער לרקע" (Minimize to Tray) מאפשר לסגור את החלון ולהשאיר את השירות פעיל ומאזין.

2. **הכתבה בלחיצה רציפה (Push-to-Talk) או נעילה בהקשה כפולה (Hands-Free Mode):**
   - **החזקה ודיבור (Push-to-Talk):** לחץ והחזק את **Right Alt / Fn (`VK_RMENU` / `VK_APPS`)**, דבר, ושחרר בסיום. הטקסט יוזרק מיד תוך פחות מ-250ms!
   - **נעילה בהקשה כפולה (Double-Tap "תק-תק"):** לחץ פעמיים מהר על **Right Alt** – ההקלטה **תינעל (Locked Mode)**, צליל נעילה יישמע וה-HUD יציג תג כחול `נעול 🔒`. תוכל להוריד את הידיים מהמקלדת ולדבר בחופשיות ללא הגבלת זמן!
   - **סיום מצב נעול:** לחיצה אחת נוספת על **Right Alt** תסיים את ההקלטה, תפתח את הנעילה ותזריק את הטקסט לחלון היעד.
   - חסימה חכמה של תפריטי Alt של Windows (מונע פתיחה בלתי רצויה של תפריטי קובץ ועריכה).

3. **חופש פעולה מלא ברקע ושמירת חלון היעד (Target Window Locking):**
   - ברגע הלחיצה על Right Alt, המערכת נועלת את ה-HWND של החלון והסמן שבו רצית לכתוב.
   - **גם אם תוך כדי דיבור לחצת בעכבר על חלון אחר, עברת לתוכנה אחרת או הקלדת במקום אחר** – ההקלטה והתמלול לא נקטעים!
   - בשחרור המקש, הפוקוס מוחזר אוטומטית לחלון המקורי והטקסט מודבק בדיוק במקום שרצית.

4. **אופטימיזציה דו-לשונית ייחודית (Hebrew & English):**
   - שימוש ב-Prompt Bias מובנה: `"שלום, Hello, מדברים בעברית ובאנגלית. תמלול מדויק כולל סימני פיסוק."`
   - Whisper מזהה ומפריד בצורה חלקה מונחים טכניים באנגלית המשולבים במשפטים בעברית.
   - שימור מלא של סימני פיסוק, פסיקים ונקודות.

5. **הזרקת יוניקוד ישירה (Unicode SendInput):**
   - הזרקת תווים באמצעות `KEYEVENTF_UNICODE` (`VK_PACKET`) ברמת ה-Win32 Kernel.
   - אינו תלוי בשפת המקלדת הפעילה (ניתן להקליד עברית גם אם מקלדת המערכת במצב אנגלית ולהיפך).
   - מונע לחלוטין שיבושי כיווניות (Bidi) ותקלות סמן.
   - גיבוי אוטומטי של הטקסט בלוח ההעתקה (Clipboard) כרשת ביטחון.

6. **עיצוב Dynamic Island יוקרתי (HUD Overlay ב-PyQt6):**
   - חלון צף מעוצב (Glassmorphism כהה) הגולש בצורה חלקה ב-60FPS מהחלק העליון המרכזי של המסך (איזור המצלמה).
   - באנר פתיחה חלק בעת הפעלת התוכנה המאשר שהמערכת מוכנה (`● מוכן / READY`).
   - מחוון מיקרופון פועם ואנימציית גלי שמע מגיבה לווליום הדיבור (Audio Waveform).
   - דגל `WS_EX_NOACTIVATE` מבטיח שה-HUD לעולם לא יגנוב פוקוס מחלון העבודה שלך.

7. **מגש מערכת (System Tray):**
   - פתיחה מחדש של ה-Control Center בלחיצה כפולה על האייקון ליד השעון.
   - החלפת מודל מהירה (small, medium, large-v3-turbo, base).
   - בחירת התקן מיקרופון.
   - היסטוריית 7 הכתבות אחרונות להעתקה בלחיצה אחת.

---

## 🚀 דרישות מערכת והתקנה

### דרישות:
- מערכת הפעלה: Windows 10 / 11 (64-bit).
- כרטיס מסך NVIDIA RTX עם תמיכת CUDA (ברירת מחדל: GeForce RTX 5060 Ti FP16) או מעבד מרובה ליבות (Fallback אוטומטי ל-CPU).
- Python 3.12 (64-bit).

### התקנה מהירה:
הפעל את הקובץ:
```cmd
install.bat
```
סקריפט זה יוצר סביבה וירטואלית (`.venv`), משדרג את `pip` ומתקין את כל התלויות כולל ספריות CUDA CuDNN ו-Faster-Whisper.

### קבצי הפעלה (Launchers):
1. **`run.bat` (הפעלה רגילה):**
   פותח את מרכז הבקרה השולחני ומפעיל את שירות ההכתבה וה-Dynamic Island HUD ברקע.
2. **`run_console.bat` (מצב דיבאג / מסוף):**
   מפעיל את השירות עם חלון שחור של שורת הפקודה המציג לוגים חיים, זיהוי מקשים ותמלולים בזמן אמת.
3. **`stop.bat`:**
   עוצר ומכבה בלחיצה אחת את כל מופעי הרקע של שירות ההכתבה.
4. **`detect_key.bat`:**
   כלי עזר מהיר לבדיקת קודי המקשים במקלדת (מזהה Fn, Alt, Apps ועוד).

---

## ⚙️ הגדרות (config.yaml)

ניתן לערוך את הקובץ `config.yaml` ישירות או דרך מרכז הבקרה / תפריט ה-Tray:

```yaml
whisper:
  model_size: "small"            # small (מהיר ומיידי), medium, large-v3-turbo, base
  device: "cuda"                 # "cuda" (NVIDIA GPU) או "cpu"
  compute_type: "float16"        # "float16" לכרטיסי RTX
  initial_prompt: "שלום, Hello, מדברים בעברית ובאנגלית. תמלול מדויק כולל סימני פיסוק."
  streaming_interval_sec: 0.6

injection:
  method: "unicode"              # הזרקה דרך SendInput ללא תלות במקלדת
  restore_target_window: true    # החזרת פוקוס לחלון היעד המקורי
  copy_to_clipboard: true        # שמירת גיבוי ב-Clipboard

hotkey:
  trigger_key: "AUTO_RIGHT"      # מגיב לכל מקש מימין לרווח (Right Alt, Fn, Apps, Right Ctrl)
  double_tap_lock_enabled: true  # נעילת דיבור חופשי בלחיצה כפולה
  double_tap_threshold_ms: 350

hud:
  enabled: true
  top_margin_px: 12
  width: 520
  height: 58

sound_cues:
  enabled: true
  volume: 0.7
```

---

## 🧪 בדיקות יחידה (Unit Tests)

להרצת בדיקות עצמאיות של רכיבי המערכת:

1. **בדיקת לכידת שמע ומיקרופון:**
   ```cmd
   .\.venv\Scripts\python.exe tests\test_audio.py
   ```
2. **בדיקת מכונת המצבים של נעילה כפולה (Double-Tap):**
   ```cmd
   .\.venv\Scripts\python.exe tests\test_double_tap.py
   ```
3. **בדיקת הזרקת טקסט Unicode:**
   ```cmd
   .\.venv\Scripts\python.exe tests\test_injector.py
   ```
4. **בדיקת מודל Whisper והאצת GPU:**
   ```cmd
   .\.venv\Scripts\python.exe tests\test_transcriber.py
   ```

---

## 📂 מבנה הקוד (Project Architecture)

```
speechtotext/
├── config.yaml               # קובץ הגדרות ראשי
├── requirements.txt          # רשימת תלויות
├── install.bat               # סקריפט התקנה אוטומטי
├── run.bat                   # סקריפט הפעלה רגיל
├── run_console.bat           # סקריפט הפעלה עם מסוף לוגים
├── stop.bat                  # סקריפט כיבוי של שירות הרקע
├── detect_key.bat            # כלי לזיהוי מקשי מקלדת
├── README.md                 # תיעוד מלא
├── src/
│   ├── main.py               # נקודת כניסה, Mutex ו-Qt Application Loop
│   ├── control_window.py     # Control Center Studio GUI
│   ├── app_controller.py     # Orchestrator לניהול תהליך ההכתבה
│   ├── window_manager.py     # נעילה ושחזור של חלון היעד (Target HWND Focus)
│   ├── keyboard_hook.py      # Win32 Low-Level Hook (Right Alt VK_RMENU / AUTO_RIGHT)
│   ├── audio_capture.py      # לכידת שמע ב-16kHz, RingBuffer ומחוון ווליום
│   ├── transcriber.py        # Faster-Whisper worker (CUDA FP16 / CPU INT8)
│   ├── injector.py           # הזרקת Unicode דרך SendInput ללא תלות במקלדת
│   ├── hud_overlay.py        # Dynamic Island HUD ב-PyQt6 (WS_EX_NOACTIVATE)
│   ├── audio_feedback.py     # צלילי חיווי נעימים מסונתזים בזיכרון
│   └── tray_app.py           # מנהל אייקון מגש המערכת והיסטוריית הכתבות
└── tests/
    ├── test_audio.py
    ├── test_double_tap.py
    ├── test_injector.py
    └── test_transcriber.py
```
