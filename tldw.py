import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLineEdit, QPushButton, QTextEdit
from PyQt5.QtGui import QFont
from PyQt5.QtCore import QCoreApplication, QThread, pyqtSignal
from youtube_transcript_api import YouTubeTranscriptApi
import re
import os 

# Convert the markdown output to html for the QT5 textbox
import markdown2

# Use local or hosted models with the OpenAI library and a custom baseurl
from openai import OpenAI

# Use .env file for configuration
from dotenv import load_dotenv
load_dotenv()

LLM_BASE_URL = os.getenv("LLM_BASE_URL")
API_KEY = os.getenv("API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME")
SYSTEM_MESSAGE = os.getenv("SYSTEM_MESSAGE")
SUMMARY_PROMPT = os.getenv("SUMMARY_PROMPT")
TEMPERATURE = float(os.getenv("TEMPERATURE"))
TOP_P = float(os.getenv("TOP_P"))
MAX_TOKENS = float(os.getenv("MAX_TOKENS"))

def llm(prompt):
    client = OpenAI(api_key=API_KEY, base_url=LLM_BASE_URL)
    messages=[{"role": "system", "content": SYSTEM_MESSAGE},{"role": "user", "content": prompt}]
    response = client.chat.completions.create(model=MODEL_NAME, max_tokens=MAX_TOKENS, temperature=TEMPERATURE, top_p=TOP_P, messages=messages)
    return response.choices[0].message.content

class LLMThread(QThread):
    """
    A QThread class to run the LLM inference in a separate thread.
    This prevents the GUI from freezing during long-running tasks.
    """
    summary_ready = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, prompt):
        super().__init__()
        self.prompt = prompt

    def run(self):
        """
        Runs the LLM inference and emits a signal when the summary is ready.
        """
        try:
            summary = llm(self.prompt)
            self.summary_ready.emit(summary)
        except Exception as e:
            self.error.emit(str(e))


class TranscriptApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Too Long, Didn't Watch")
        self.setGeometry(100, 100, 800, 600)  # Large window size

        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Set default font
        default_font = QFont()
        default_font.setPointSize(12)  # Increase base font size

        # Create URL input with larger text
        self.url_input = QLineEdit()
        self.url_input.setFont(default_font)
        self.url_input.setPlaceholderText("Paste YouTube URL here")
        layout.addWidget(self.url_input)

        # Create button with larger text
        self.fetch_button = QPushButton("Summarize Video")
        self.fetch_button.setFont(default_font)
        self.fetch_button.clicked.connect(self.fetch_transcript)
        layout.addWidget(self.fetch_button)

        # The transcript_display can accept HTML
        self.transcript_display = QTextEdit()
        self.transcript_display.setFont(default_font)
        self.transcript_display.setReadOnly(True)
        self.transcript_display.setAcceptRichText(True)  # Enable rich text
        layout.addWidget(self.transcript_display)

        self.llm_thread = None # Initialize the LLM thread

    def extract_video_id(self, url):
        # Extract video ID from various YouTube URL formats
        video_id_match = re.search(r'(?:v=|/)([\w-]{11})', url)
        if video_id_match:
            return video_id_match.group(1)
        return None

    def fetch_transcript(self):
        self.transcript_display.setText("Fetching transcript...")
        self.transcript_display.repaint()
        QCoreApplication.processEvents()  # Process pending events
        url = self.url_input.text()
        video_id = self.extract_video_id(url)
        
        if not video_id:
            self.transcript_display.setText("Invalid YouTube URL")
            return

        try:
            transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['en', 'en-US'])
            # Extract just the text from the transcript
            text_only = ' '.join([entry['text'] for entry in transcript])
            self.transcript_display.setText("Thinking...")
            self.transcript_display.repaint()
            QCoreApplication.processEvents()  # Process pending events
            prompt = SUMMARY_PROMPT.format(transcript=text_only)

            # Start the LLM thread
            self.llm_thread = LLMThread(prompt)
            self.llm_thread.summary_ready.connect(self.update_summary)
            self.llm_thread.error.connect(self.show_error)
            self.llm_thread.start()


        except Exception as e:
            self.transcript_display.setText(f"Error fetching transcript: {str(e)}")

    def update_summary(self, video_summary):
         """
         Updates the transcript display with the summary from the LLM.
         This method is called when the LLM thread finishes successfully.
         """
         html_content = markdown2.markdown(video_summary)
         self.transcript_display.setText(html_content)
         self.llm_thread = None  # Reset the thread

    def show_error(self, message):
        """
        Displays an error message in the transcript display.
        This method is called when the LLM thread encounters an error.
        """
        self.transcript_display.setText(f"Error generating summary: {message}")
        self.llm_thread = None  # Reset the thread


def main():
    app = QApplication(sys.argv)
    
    # Set application-wide default font size
    default_font = QFont()
    default_font.setPointSize(12)  # Increase base font size
    app.setFont(default_font)
    
    window = TranscriptApp()
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()