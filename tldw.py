import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QLineEdit, QPushButton, QTextEdit, QTabWidget,
                            QDialog, QFormLayout, QDialogButtonBox)
from PyQt5.QtGui import QFont
from PyQt5.QtCore import QCoreApplication, QThread, pyqtSignal, QSettings
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

# Initialize QSettings
settings = QSettings("TLDW", "VideoSummarizer")

# Load defaults from environment or use hardcoded defaults
LLM_BASE_URL = settings.value("llm_base_url", os.getenv("LLM_BASE_URL", "http://localhost:8080/v1"))
API_KEY = settings.value("api_key", os.getenv("API_KEY", "doesntmatter"))
MODEL_NAME = settings.value("model_name", os.getenv("MODEL_NAME", "doesntmatter"))
SYSTEM_MESSAGE = settings.value("system_message", os.getenv("SYSTEM_MESSAGE", "You summarizes video transcripts"))
SUMMARY_PROMPT = settings.value("summary_prompt", os.getenv("SUMMARY_PROMPT", "Video Transcript: {transcript}\n\nSummarize the above transcript in markdown format with key topics and interesting quotes"))

def llm(prompt):
    client = OpenAI(api_key=API_KEY, base_url=LLM_BASE_URL, timeout=300)
    messages=[{"role": "system", "content": SYSTEM_MESSAGE},{"role": "user", "content": prompt}]
    response = client.chat.completions.create(model=MODEL_NAME, messages=messages)
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

        # Create status bar
        self.statusBar = self.statusBar()
        self.statusBar.showMessage("Ready to Summarize")

        # Set default font
        default_font = QFont()
        default_font.setPointSize(12)  # Increase base font size

        # Create URL input with larger text
        self.url_input = QLineEdit()
        self.url_input.setFont(default_font)
        self.url_input.setPlaceholderText("Paste YouTube URL here")
        layout.addWidget(self.url_input)

        # Create buttons with larger text
        button_layout = QVBoxLayout()
        
        self.fetch_button = QPushButton("Summarize Video")
        self.fetch_button.setFont(default_font)
        self.fetch_button.clicked.connect(self.fetch_transcript)
        button_layout.addWidget(self.fetch_button)
        
        self.config_button = QPushButton("Configuration")
        self.config_button.setFont(default_font)
        self.config_button.clicked.connect(self.show_config_dialog)
        button_layout.addWidget(self.config_button)
        
        layout.addLayout(button_layout)

        # Create tab widget for formatted and raw views
        self.tab_widget = QTabWidget()
        
        # Formatted HTML tab
        self.formatted_display = QTextEdit()
        self.formatted_display.setFont(default_font)
        self.formatted_display.setReadOnly(True)
        self.formatted_display.setAcceptRichText(True)
        
        # Raw markdown tab
        self.raw_display = QTextEdit()
        self.raw_display.setFont(default_font)
        self.raw_display.setReadOnly(True)
        
        # Add tabs
        self.tab_widget.addTab(self.formatted_display, "Formatted")
        self.tab_widget.addTab(self.raw_display, "Raw Markdown")
        
        layout.addWidget(self.tab_widget)

        self.llm_thread = None # Initialize the LLM thread

    def extract_video_id(self, url):
        # Extract video ID from various YouTube URL formats
        video_id_match = re.search(r'(?:v=|/)([\w-]{11})', url)
        if video_id_match:
            return video_id_match.group(1)
        return None

    def fetch_transcript(self):
        self.statusBar.showMessage("Fetching transcript...")
        self.formatted_display.setText("Fetching transcript...")
        self.raw_display.setText("")
        self.formatted_display.repaint()
        QCoreApplication.processEvents()  # Process pending events
        url = self.url_input.text()
        video_id = self.extract_video_id(url)
        
        if not video_id:
            self.formatted_display.setText("Invalid YouTube URL")
            return

        try:
            transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['en', 'en-US'])
            # Extract just the text from the transcript
            text_only = ' '.join([entry['text'] for entry in transcript])
            transcript_size = len(text_only)
            self.statusBar.showMessage(f"Transcript size: {transcript_size} bytes. Processing...")
            self.formatted_display.setText("Thinking...")
            self.raw_display.setText("")
            self.formatted_display.repaint()
            QCoreApplication.processEvents()  # Process pending events
            prompt = SUMMARY_PROMPT.format(transcript=text_only)

            # Start the LLM thread
            self.llm_thread = LLMThread(prompt)
            self.llm_thread.summary_ready.connect(self.update_summary)
            self.llm_thread.error.connect(self.show_error)
            self.llm_thread.start()


        except Exception as e:
            self.formatted_display.setText(f"Error fetching transcript: {str(e)}")

    def update_summary(self, video_summary):
        """
        Updates both tabs with the summary from the LLM.
        This method is called when the LLM thread finishes successfully.
        """
        html_content = markdown2.markdown(video_summary)
        self.formatted_display.setText(html_content)
        self.raw_display.setText(video_summary)
        self.statusBar.showMessage("Ready to Summarize")
        self.llm_thread = None  # Reset the thread

    def show_error(self, message):
        """
        Displays an error message in both tabs.
        This method is called when the LLM thread encounters an error.
        """
        error_msg = f"Error generating summary: {message}"
        self.formatted_display.setText(error_msg)
        self.raw_display.setText(error_msg)
        self.statusBar.showMessage("Ready to Summarize")
        self.llm_thread = None  # Reset the thread

    def show_config_dialog(self):
        dialog = ConfigDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            values = dialog.get_values()
            settings.setValue("llm_base_url", values["llm_base_url"])
            settings.setValue("api_key", values["api_key"])
            settings.setValue("model_name", values["model_name"])
            settings.setValue("system_message", values["system_message"])
            settings.setValue("summary_prompt", values["summary_prompt"])
            
            # Update global variables
            global LLM_BASE_URL, API_KEY, MODEL_NAME, SYSTEM_MESSAGE, SUMMARY_PROMPT
            LLM_BASE_URL = values["llm_base_url"]
            API_KEY = values["api_key"]
            MODEL_NAME = values["model_name"]
            SYSTEM_MESSAGE = values["system_message"]
            SUMMARY_PROMPT = values["summary_prompt"]

class ConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuration")
        
        layout = QFormLayout(self)
        
        self.llm_base_url = QLineEdit(LLM_BASE_URL)
        self.api_key = QLineEdit(API_KEY)
        self.model_name = QLineEdit(MODEL_NAME)
        self.system_message = QTextEdit(SYSTEM_MESSAGE)
        self.summary_prompt = QTextEdit(SUMMARY_PROMPT)
        
        layout.addRow("LLM Base URL:", self.llm_base_url)
        layout.addRow("API Key:", self.api_key)
        layout.addRow("Model Name:", self.model_name)
        layout.addRow("System Message:", self.system_message)
        layout.addRow("Summary Prompt:", self.summary_prompt)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        
        layout.addRow(buttons)
        
    def get_values(self):
        return {
            "llm_base_url": self.llm_base_url.text(),
            "api_key": self.api_key.text(),
            "model_name": self.model_name.text(),
            "system_message": self.system_message.toPlainText(),
            "summary_prompt": self.summary_prompt.toPlainText()
        }


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
