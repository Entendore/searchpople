import sys
import html
from urllib.parse import urlparse

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextBrowser, QMessageBox
)
from PySide6.QtCore import Qt, QThread, Signal
from duckduckgo_search import DDGS
from duckduckgo_search.exceptions import RatelimitException, TimeoutException


class SearchWorker(QThread):
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, query: str):
        super().__init__()
        self.query = query

    def run(self):
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(self.query, max_results=15))
                self.finished.emit(results)
        except (RatelimitException, TimeoutException) as e:
            self.error.emit(f"Search service busy or timed out: {e}. Try again shortly.")
        except Exception as e:
            self.error.emit(f"{type(e).__name__}: {e}")


class WebSearchApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Public Web Information Lookup")
        self.resize(820, 620)
        self.worker = None

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        row = QHBoxLayout()
        row.addWidget(QLabel("Enter Name or Identifier:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("e.g., 'Jane Doe site:linkedin.com'")
        self.search_input.returnPressed.connect(self.perform_search)
        self.search_button = QPushButton("Search Web")
        self.search_button.clicked.connect(self.perform_search)
        row.addWidget(self.search_input, stretch=1)
        row.addWidget(self.search_button)
        layout.addLayout(row)

        self.results_area = QTextBrowser()
        self.results_area.setReadOnly(True)
        self.results_area.setOpenExternalLinks(True)
        layout.addWidget(self.results_area, stretch=1)

        self.statusBar().showMessage("Ready")

    # --- search flow ---
    def perform_search(self):
        query = self.search_input.text().strip()
        if not query:
            QMessageBox.warning(self, "Input Error", "Please enter a search term.")
            return

        if self.worker and self.worker.isRunning():
            self.worker.wait(2000)

        self.search_button.setEnabled(False)
        self.search_input.setEnabled(False)
        self.statusBar().showMessage(f"Searching for: {query}...")
        self.results_area.setHtml("<i>Fetching results…</i>")

        self.worker = SearchWorker(query)
        self.worker.finished.connect(self.display_results)
        self.worker.error.connect(self.show_error)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.error.connect(self.worker.deleteLater)
        self.worker.start()

    def _safe_url(self, url: str) -> str:
        if not url:
            return "#"
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https", ""):
            return "#"
        return html.escape(url, quote=True)

    def display_results(self, results):
        self.results_area.clear()
        if not results:
            self.results_area.setPlainText("No public information found.")
            self._reset_ui()
            return

        parts = ["<h2>Search Results</h2><hr>"]
        for item in results:
            title = html.escape(item.get("title", "No Title"))
            snippet = html.escape(item.get("body", "No snippet available."))
            url = self._safe_url(item.get("href") or item.get("link") or "")
            parts.append(
                f"<div style='margin-bottom:15px;'>"
                f"<h3 style='margin:0;'><a href='{url}' style='color:#1a0dab;text-decoration:none;'>{title}</a></h3>"
                f"<p style='color:#4d5156;margin:5px 0;'>{snippet}</p>"
                f"<p style='color:#006621;font-size:11px;margin:0;'>{url}</p>"
                f"</div><hr>"
            )
        self.results_area.setHtml("".join(parts))
        self.statusBar().showMessage(f"Found {len(results)} results.", 5000)
        self._reset_ui()

    def show_error(self, msg):
        self.results_area.setPlainText(f"Search failed:\n{msg}")
        self._reset_ui()

    def _reset_ui(self):
        self.search_button.setEnabled(True)
        self.search_input.setEnabled(True)
        self.search_input.setFocus()

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.wait(3000)
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = WebSearchApp()
    win.show()
    sys.exit(app.exec())