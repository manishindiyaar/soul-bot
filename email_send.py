import os
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

# -------------------------- #
#  SUPABASE IMPORT & SETUP   #
# -------------------------- #
from supabase import create_client, Client

SUPABASE_URL = "https://nryaarklafuymrwxhgdn.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5yeWFhcmtsYWZ1eW1yd3hoZ2RuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MzQ5MjgxMDQsImV4cCI6MjA1MDUwNDEwNH0.CI6LQFVpparoPEd1ta9OKJKK31SDQsXSErgng_8U7y8"

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_last_inserted_patient() -> Optional[dict]:
    """
    Fetch the most recently created patient record from the 'patients' table.
    Returns a dict like:
      {
        "id": ...,
        "name": "...",
        "date_of_birth": "...",
        ...,
        "created_at": "..."
      }
    or None if no records exist.
    """
    response = (
        supabase
        .table("patients")
        .select("*")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if response.data and len(response.data) > 0:
        return response.data[0]
    return None

# -------------------------- #
#  SENDGRID IMPORT & SETUP   #
# -------------------------- #
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content

load_dotenv()

LOGS_FOLDER = r"C:\Users\Aadidev\Desktop\SoulBotHackathon\backend\conversation logs"

def get_newest_json_file(folder_path: str) -> Optional[str]:
    """Returns the path of the newest .json file in the given folder, or None if none found."""
    if not os.path.isdir(folder_path):
        return None
    
    json_files = [
        os.path.join(folder_path, f)
        for f in os.listdir(folder_path)
        if f.lower().endswith(".json")
    ]
    if not json_files:
        return None

    # Sort by creation time (descending), then pick the newest
    json_files.sort(key=os.path.getctime, reverse=True)
    return json_files[0]

def parse_conversation_json(file_path: str) -> List[Dict[str, Any]]:
    """
    Reads a JSON file containing conversation messages like:
        [
          { "role": "...", "content": "..." },
          ...
        ]
    Ensures 'content' is always a string (flattening any list).
    Returns a list of dicts with 'role' and 'content'.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        conversation_data = json.load(f)

    parsed_data = []
    for entry in conversation_data:
        role = entry.get("role", "")
        content = entry.get("content", "")

        # If 'content' is a list, flatten into one string
        if isinstance(content, list):
            content = " ".join(content)

        parsed_data.append({
            "role": role,
            "content": content
        })

    return parsed_data

def generate_personalized_html(
    conversation_data: List[Dict[str, str]],
    user_name: str,
    date_of_birth: str = "15/08/2006",
    birth_time: str = "10:00 AM",
    place_of_birth: str = "Mumbai"
) -> str:
    """
    Builds an astrology-themed HTML email, incorporating the last user and assistant messages
    plus the dynamic 'user_name' from Supabase or fallback defaults.
    """
    # Extract user and assistant messages
    user_messages = [msg['content'] for msg in conversation_data if msg['role'] == 'user']
    assistant_messages = [msg['content'] for msg in conversation_data if msg['role'] == 'assistant']

    # Grab the last user and assistant messages (if available)
    last_user_message = user_messages[-1] if user_messages else "No user messages found."
    last_assistant_message = assistant_messages[-1] if assistant_messages else "No assistant replies found."

    # Example HTML content
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{
            font-family: Arial, sans-serif;
            background: linear-gradient(to bottom, #2b1055, #7597de);
            margin: 0;
            padding: 0;
            color: black;
        }}
        .container {{
            max-width: 600px;
            margin: 20px auto;
            background-color: rgba(255, 255, 255, 0.9);
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0px 4px 8px rgba(0, 0, 0, 0.2);
        }}
        .header {{
            text-align: center;
            font-size: 18px;
            font-weight: bold;
            margin-bottom: 20px;
            color: #2b1055;
        }}
        .section {{
            margin-bottom: 20px;
        }}
        .section-title {{
            font-size: 16px;
            font-weight: bold;
            margin-bottom: 10px;
            color: #2b1055;
        }}
        .prediction-box {{
            display: inline-block;
            width: 30%;
            text-align: center;
            padding: 20px;
            border: 1px solid #ddd;
            border-radius: 8px;
            margin: 5px;
            background-color: #f8f8f8;
            color: #2b1055;
            vertical-align: top;
        }}
        .prediction-box-content {{
            margin-top: 10px;
            font-size: 14px;
        }}
        .recommendation-box {{
            margin-bottom: 10px;
            color: #2b1055;
        }}
        .recommendation-box p {{
            margin: 5px 0;
        }}
        .daily-practice {{
            display: block;
            width: 100%;
            text-align: left;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            margin: 5px 0;
            background-color: #f8f8f8;
        }}
        .daily-practice-content {{
            font-size: 14px;
            color: #2b1055;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            Dear {user_name} ⭐<br><br>
            Here’s your personalized spiritual guidance based on your recent conversation
            and your birth details ({date_of_birth} - {birth_time}, {place_of_birth}).
        </div>
        <hr>
        
        <div class="section">
            <p><strong>Your last message:</strong> {last_user_message}</p>
            <p><strong>Soul-Bot's reply:</strong> {last_assistant_message}</p>
        </div>
        <hr>

        <div class="section">
            <p><b>Sun Sign ☀️:</b> Leo (based on 15/08/2006). Leadership and radiance guide you.</p>
            <p><b>Moon Sign 🌙:</b> Aries, influencing emotional drive and spontaneity.</p>
            <p><b>Ruling Planet 🔆:</b> The Sun, shaping self-expression and confidence.</p>
        </div>
        <hr>

        <div class="section">
            <div class="section-title">Key Predictions 🔮</div>
            <div class="prediction-box">
                Career and Finances 💼
                <div class="prediction-box-content">
                    You may find fresh opportunities this month; keep your passion focused.
                </div>
            </div>
            <div class="prediction-box">
                Relationships & Family 🤝
                <div class="prediction-box-content">
                    Open-hearted communication leads to stronger bonds.
                </div>
            </div>
            <div class="prediction-box">
                Personal Growth 🌱
                <div class="prediction-box-content">
                    Harness your natural optimism for learning new skills.
                </div>
            </div>
            <div class="prediction-box">
                Health & Well-being 💪
                <div class="prediction-box-content">
                    Balance work and rest, as mindfulness can keep stress in check.
                </div>
            </div>
        </div>
        <hr>
        
        <div class="section">
            <div class="section-title">Recommendations 🪄</div>
            <div class="recommendation-box">
                <b>Gemstone Suggestions 💎:</b>
                <p>
                    Ruby is often suggested for Leo natives, enhancing self-confidence.
                </p>
            </div>
            <div class="recommendation-box">
                <b>Pooja/Rituals 🙏:</b>
                <p>
                    Surya Namaskar or morning affirmations to harness solar energy.
                </p>
            </div>
            <div class="recommendation-box">
                <b>Do's and Don'ts ✅❌:</b>
                <p><b>Do:</b> Embrace leadership roles; you're naturally suited for them.</p>
                <p><b>Don't:</b> Neglect self-care. Too much pride can lead to burnout.</p>
            </div>
        </div>
        <hr>
        
        <div class="section">
            <div class="section-title">Daily Practices 🌞</div>
            <div class="daily-practice">
                <div class="daily-practice-content">
                    <b>Meditation/Workout 🧘:</b> 10-15 minutes daily to channel your fiery energy into a calm focus.
                </div>
            </div>
            <div class="daily-practice">
                <div class="daily-practice-content">
                    <b>Sleep Rituals 😴:</b> Unplug from screens and tension, giving space for a serene night's rest.
                </div>
            </div>
        </div>
        <hr>
    </div>
</body>
</html>
"""
    return html_content

def send_email(to_email: str, body_content: str, subject: str) -> dict:
    """Send an email using SendGrid."""
    sg_api_key = os.getenv('SENDGRID_API_KEY')
    from_addr = os.getenv('MAIL_DEFAULT_SENDER')
    from_name = os.getenv('MAIL_DEFAULT_SENDER_NAME', 'Appointment System')

    if not sg_api_key:
        return {'status': 'error', 'message': 'SENDGRID_API_KEY is not set'}

    sg = SendGridAPIClient(api_key=sg_api_key)
    from_email = Email(email=from_addr, name=from_name)

    message = Mail(
        from_email=from_email,
        to_emails=To(to_email),
        subject=subject,
        html_content=Content("text/html", body_content)
    )

    try:
        sg.send(message)
        return {'status': 'success', 'message': f'Email sent successfully to {to_email}'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

def email_send(to_email: str, subject: str) -> None:
    """ 
    1. Dynamically retrieve the last inserted patient from Supabase for user_name (or other info).
    2. Find the newest .json file in LOGS_FOLDER.
    3. Parse conversation data.
    4. Generate personalized HTML from it (using the dynamic user_name).
    5. Send the email via SendGrid.
    """
    # 1) Grab the last inserted patient from supabase
    patient = get_last_inserted_patient()
    if patient is None:
        print("No patient record found in 'patients' table. Using fallback name.")
        user_name = "Aadidev"
    else:
        # Adjust this based on your actual table schema:
        user_name = patient.get("name", "Aadidev")

    # 2) Find newest conversation log
    newest_file = get_newest_json_file(LOGS_FOLDER)
    if not newest_file:
        print("No .json files found in the conversation logs folder.")
        return

    print(f"Newest JSON file found: {newest_file}")
    conversation_data = parse_conversation_json(newest_file)

    # 3) Generate HTML with user + assistant messages, plus dynamic user_name
    body_content = generate_personalized_html(conversation_data, user_name=user_name)

    # 4) Send the email
    result = send_email(to_email=to_email, body_content=body_content, subject=subject)
    print(f"Send Email Result: {result}")

if __name__ == "__main__":
    # If run directly, use these defaults:
    recipient_email = "aadidevraizada26@gmail.com"
    email_subject = "Your Personalized Soul-Bot Reading"
    email_send(to_email=recipient_email, subject=email_subject)
