import sys
from PyQt6.QtWidgets import QApplication

from browser.browser import Browser
from lib.llm_api import SingletonLLMConnect
from lib.llm_browser_integration import BrowserLLMIntegration


def main():
    # Initialize Qt Application
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # Set modern style

    try:
        # Initialize LLM client
        print("Initializing LLM client...")
        llm_client = SingletonLLMConnect()

        # Create browser window
        print("Creating browser window...")
        browser = Browser()

        # Setup LLM integration
        print("Setting up LLM integration...")
        llm_integration = BrowserLLMIntegration(browser, llm_client)

        # Show browser window
        browser.show()

        # Start Qt event loop
        print("Application started successfully!")
        return app.exec()

    except Exception as e:
        print(f"Error starting application: {str(e)}")
        return 1


if __name__ == '__main__':
    sys.exit(main())