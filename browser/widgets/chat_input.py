from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTextEdit


class ChatInput(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(60)
        self.setPlaceholderText("Ask me anything... (Press Enter to send, Shift+Enter for new line)")

    def keyPressEvent(self, event):
        # Check for Enter key
        if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            # Check if Shift is being held
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                # Insert new line
                super().keyPressEvent(event)
            else:
                # Emit return pressed signal for sending
                self.parent().send_message()
                # Don't call super().keyPressEvent to prevent new line
                return
        else:
            # Handle all other keys normally
            super().keyPressEvent(event)