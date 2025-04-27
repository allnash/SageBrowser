from PyQt6.QtCore import pyqtSignal, Qt, QTimer
from PyQt6.QtWidgets import QVBoxLayout, QWidget, QScrollArea, QHBoxLayout, QPushButton

from browser.widgets.chat_input import ChatInput
from browser.widgets.chat_message import ChatMessage


class ChatWindow(QWidget):
    message_sent = pyqtSignal(str)
    browser_command = pyqtSignal(str, dict)  # Signal for browser commands

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_response = None
        self.command_prefix = "/"  # Define command prefix
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
        if not message:
            return

        # Check if message is a command
        if message.startswith(self.command_prefix):
            self.add_message(message, True)  # Show command in chat
            self.handle_browser_command(message)
        else:
            self.add_message(message, True)
            self.message_sent.emit(message)

        self.message_input.clear()
        self.current_response = None

    def handle_browser_command(self, command_text):
        """Handle browser control commands"""
        # Strip prefix and split into command and arguments
        parts = command_text[len(self.command_prefix):].strip().split(" ", 1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        # Command dictionary - maps commands to handlers
        commands = {
            "goto": self.cmd_goto,
            "back": self.cmd_back,
            "forward": self.cmd_forward,
            "reload": self.cmd_reload,
            "fillform": self.cmd_fill_form,
            "click": self.cmd_click,
            "type": self.cmd_type,
            "submit": self.cmd_submit,
            "help": self.cmd_help,
            "debug": self.cmd_debug,
            # New commands for form elements
            "select": self.cmd_select,
            "radio": self.cmd_radio,
            "checkbox": self.cmd_checkbox,
            "custom": self.cmd_custom,
        }

        if command in commands:
            commands[command](args)
        else:
            self.add_message(f"Unknown command: {command}. Type /help for available commands.", False)

    def cmd_goto(self, args):
        """Navigate to URL"""
        if not args:
            self.add_message("Usage: /goto [url]", False)
            return
        self.browser_command.emit("goto", {"url": args})
        self.add_message(f"Navigating to {args}...", False)

    def cmd_back(self, args):
        """Go back in history"""
        self.browser_command.emit("back", {})
        self.add_message("Going back...", False)

    def cmd_forward(self, args):
        """Go forward in history"""
        self.browser_command.emit("forward", {})
        self.add_message("Going forward...", False)

    def cmd_reload(self, args):
        """Reload page"""
        self.browser_command.emit("reload", {})
        self.add_message("Reloading page...", False)

    def cmd_fill_form(self, args):
        """Fill a form with provided data"""
        if not args:
            self.add_message("Usage: /fillform [JSON data or field=value pairs]", False)
            return

        try:
            # Try to parse as JSON
            import json
            form_data = json.loads(args)
        except json.JSONDecodeError:
            # Parse as field=value pairs
            form_data = {}
            pairs = args.split(",")
            for pair in pairs:
                if "=" in pair:
                    key, value = pair.split("=", 1)
                    form_data[key.strip()] = value.strip()

        if not form_data:
            self.add_message("No valid form data provided", False)
            return

        self.browser_command.emit("fillform", {"data": form_data})
        self.add_message(f"Filling form with data: {form_data}", False)

    def cmd_click(self, args):
        """Click on an element by selector"""
        if not args:
            self.add_message("Usage: /click [CSS selector or element text]", False)
            return
        self.browser_command.emit("click", {"selector": args})
        self.add_message(f"Clicking on element: {args}", False)

    def cmd_type(self, args):
        """Type into an input field"""
        # Improved parsing for fields with spaces
        # Support for both syntax: /type "Full Name" Nash and /type Full Name:Nash

        if ":" in args:
            # Format: Field:Value
            parts = args.split(":", 1)
            if len(parts) < 2:
                self.add_message("Usage: /type [field]:[text] or /type \"[field]\" [text]", False)
                return
            selector, text = parts[0].strip(), parts[1].strip()
        elif '"' in args:
            # Format: "Field" Value
            import re
            match = re.match(r'"([^"]+)"\s+(.*)', args)
            if not match:
                self.add_message('Usage: /type [field]:[text] or /type "[field]" [text]', False)
                return
            selector, text = match.group(1), match.group(2)
        else:
            # Simple fallback - no hardcoded field names
            # Just use first word as selector and the rest as text
            # This is unreliable but provides backward compatibility
            parts = args.split(" ")
            if len(parts) < 2:
                self.add_message('Usage: /type [field]:[text] or /type "[field]" [text]', False)
                return

            # Fallback to simple splitting
            selector, text = parts[0], " ".join(parts[1:])

        self.browser_command.emit("type", {"selector": selector, "text": text})
        self.add_message(f"Typing '{text}' into '{selector}'", False)

    def cmd_select(self, args):
        """Select an option from a dropdown"""
        if not args or ":" not in args:
            self.add_message("Usage: /select [selector]:[option]", False)
            return

        parts = args.split(":", 1)
        selector = parts[0].strip()
        option = parts[1].strip()

        if not selector or not option:
            self.add_message("Both selector and option value are required", False)
            return

        self.browser_command.emit("select", {"selector": selector, "value": option})
        self.add_message(f"Selecting option '{option}' from '{selector}'", False)

    def cmd_radio(self, args):
        """Select a radio button"""
        if not args:
            self.add_message("Usage: /radio [selector] or /radio [selector]:[value]", False)
            return

        if ":" in args:
            parts = args.split(":", 1)
            selector = parts[0].strip()
            value = parts[1].strip()
        else:
            selector = args.strip()
            value = None

        if not selector:
            self.add_message("Selector is required", False)
            return

        self.browser_command.emit("radio", {"selector": selector, "value": value})
        if value:
            self.add_message(f"Selecting radio button '{selector}' with value '{value}'", False)
        else:
            self.add_message(f"Selecting radio button '{selector}'", False)

    def cmd_checkbox(self, args):
        """Check or uncheck a checkbox"""
        if not args:
            self.add_message("Usage: /checkbox [selector] or /checkbox [selector]:[true/false]", False)
            return

        if ":" in args:
            parts = args.split(":", 1)
            selector = parts[0].strip()
            value_str = parts[1].strip().lower()
            check = value_str in ("true", "yes", "1", "on")
        else:
            selector = args.strip()
            check = True  # Default to checking

        if not selector:
            self.add_message("Selector is required", False)
            return

        self.browser_command.emit("checkbox", {"selector": selector, "check": check})
        action = "Checking" if check else "Unchecking"
        self.add_message(f"{action} checkbox '{selector}'", False)

    def cmd_custom(self, args):
        """Click a custom element"""
        if not args:
            self.add_message("Usage: /custom [selector] or /custom [selector]:[attribute]:[value]", False)
            return

        parts = args.split(":")

        if len(parts) == 1:
            selector = parts[0].strip()
            attribute = None
            value = None
        elif len(parts) == 2:
            selector = parts[0].strip()
            value = parts[1].strip()
            attribute = None
        elif len(parts) >= 3:
            selector = parts[0].strip()
            attribute = parts[1].strip()
            value = parts[2].strip()

        if not selector:
            self.add_message("Selector is required", False)
            return

        self.browser_command.emit("custom", {"selector": selector, "attribute": attribute, "value": value})

        message = f"Clicking custom element '{selector}'"
        if attribute and value:
            message += f" with {attribute}='{value}'"
        elif value:
            message += f" with value='{value}'"

        self.add_message(message, False)

    def cmd_submit(self, args):
        """Submit a form"""
        selector = args if args else "form"
        self.browser_command.emit("submit", {"selector": selector})
        self.add_message(f"Submitting form: {selector}", False)

    def cmd_help(self, args):
        """Show help for commands"""
        help_text = """
    Available browser commands:
    /goto [url] - Navigate to URL
    /back - Go back in history
    /forward - Go forward in history
    /reload - Reload current page
    /fillform [data] - Fill form fields (JSON or field=value,field2=value2)
    /type [field]:[text] - Type text into field (use colon to separate)
    /type "[field]" [text] - Type text into field (use quotes for fields with spaces)
    /click [text] - Click on element with text or button
    /submit - Submit a form
    /debug [selector] - Debug element properties

    Form element commands:
    /select [selector]:[option] - Select an option from a dropdown 
    /radio [name]:[value] - Select a radio button with specified value
    /checkbox [selector]:[true/false] - Check or uncheck a checkbox
    /custom [selector]:[attribute]:[value] - Click a custom element like star ratings

    /help - Show this help
    """
        self.add_message(help_text, False)

    def cmd_debug(self, args):
        """Debug an element's properties"""
        if not args:
            self.add_message("Usage: /debug [CSS selector]", False)
            return

        self.browser_command.emit("debug", {"selector": args})
        self.add_message(f"Debugging element: {args}", False)

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