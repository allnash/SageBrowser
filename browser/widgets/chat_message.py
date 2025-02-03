# browser/widgets/chat_message.py
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QLabel
from datetime import datetime


class ChatMessage(QFrame):
    def __init__(self, message: str, is_user: bool = True, parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        layout = QVBoxLayout(self)

        # Message header
        header = QLabel("You" if is_user else "Assistant")
        header.setStyleSheet("font-weight: bold; color: #555;")

        # Message content - keep reference to update later
        self.content = QLabel(message)
        self.content.setWordWrap(True)
        self.content.setStyleSheet("color: #000;")

        # Timestamp
        timestamp = QLabel(datetime.now().strftime("%H:%M"))
        timestamp.setStyleSheet("color: #999; font-size: 10px;")

        layout.addWidget(header)
        layout.addWidget(self.content)
        layout.addWidget(timestamp)

        # Style the message bubble
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {'#DCF8C6' if is_user else '#E8E8E8'};
                border-radius: 10px;
                padding: 5px;
                margin: 5px;
            }}
        """)