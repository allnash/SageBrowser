from PyQt6.QtCore import pyqtSignal, Qt, QTimer
from PyQt6.QtWidgets import QVBoxLayout, QWidget, QScrollArea, QHBoxLayout, QPushButton

from browser.widgets.chat_input import ChatInput
from browser.widgets.chat_message import ChatMessage


class ChatWindow(QWidget):
    message_sent = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_response = None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Chat history area
        self.chat_area = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_area)
        self.chat_layout.addStretch()

        # Scroll area for chat
        scroll = QScrollArea()
        scroll.setWidget(self.chat_area)
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Input area
        input_layout = QHBoxLayout()
        self.message_input = ChatInput(self)  # Using custom ChatInput
        send_button = QPushButton("Send")
        send_button.clicked.connect(self.send_message)

        input_layout.addWidget(self.message_input)
        input_layout.addWidget(send_button)

        layout.addWidget(scroll)
        layout.addLayout(input_layout)

    def send_message(self):
        message = self.message_input.toPlainText().strip()
        if message:
            self.add_message(message, True)
            self.message_sent.emit(message)
            self.message_input.clear()
            # Reset current response for new conversation
            self.current_response = None

    def add_message(self, message: str, is_user: bool = True):
        if is_user:
            # For user messages, always create a new message widget
            message_widget = ChatMessage(message, is_user)
            self.chat_layout.addWidget(message_widget)
            self.current_response = None
        else:
            # For assistant messages
            if self.current_response is None:
                # Create new message widget for first assistant response
                self.current_response = ChatMessage(message, is_user)
                self.chat_layout.addWidget(self.current_response)
            else:
                # Update existing message content
                current_text = self.current_response.content.text()
                self.current_response.content.setText(current_text + message)

        # Force scroll to bottom
        QTimer.singleShot(0, lambda: self.scroll_to_bottom())

    def scroll_to_bottom(self):
        scroll = self.findChild(QScrollArea)
        if scroll:
            scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())