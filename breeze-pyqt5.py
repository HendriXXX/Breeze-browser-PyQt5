import sys
import platform
import os
from PyQt5.QtCore import QUrl, QSettings, QT_VERSION_STR
from PyQt5.QtWidgets import QApplication, QMainWindow, QTabWidget, QLineEdit, QToolBar, QAction, QMenu, QToolButton, QMessageBox, QFileDialog, QProgressBar, QPushButton, QDialog, QFormLayout, QDialogButtonBox
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings, QWebEngineProfile, QWebEngineDownloadItem, QWebEnginePage

class RenameBookmarkDialog(QDialog):
    def __init__(self, name, url, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Rename Bookmark')

        self.name_edit = QLineEdit(name)
        self.url_edit = QLineEdit(url)

        form_layout = QFormLayout()
        form_layout.addRow('Name:', self.name_edit)
        form_layout.addRow('URL:', self.url_edit)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        layout = QFormLayout(self)
        layout.addRow(form_layout)
        layout.addRow(self.button_box)

    def get_data(self):
        return self.name_edit.text(), self.url_edit.text()

class Browser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings("breeze")
        self.bookmarks = self.settings.value("bookmarks", [])
        self.convert_old_bookmark_format()
        self.init_ui()
        self.show()

    def convert_old_bookmark_format(self):
        updated_bookmarks = []
        for bookmark in self.bookmarks:
            if isinstance(bookmark, str):
                updated_bookmarks.append({'name': bookmark, 'url': bookmark})
            else:
                updated_bookmarks.append(bookmark)
        self.bookmarks = updated_bookmarks
        self.settings.setValue("bookmarks", self.bookmarks)

    def init_ui(self):
        self.init_tabs()
        self.init_toolbar()
        self.init_statusbar()
        self.set_initial_window_size()
        self.add_new_tab(QUrl("https://duckduckgo.com"), "Homepage")
        self.update_bookmarks_menu()

    def init_tabs(self):
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.tabBarDoubleClicked.connect(self.tab_open_doubleclick)
        self.tabs.currentChanged.connect(self.current_tab_changed)
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_current_tab)
        self.tabs.setStyleSheet("QTabBar::tab { width: 185px; }")
        self.setCentralWidget(self.tabs)

    def init_toolbar(self):
        navtb = QToolBar("Navigation")
        self.addToolBar(navtb)

        self.add_toolbar_button(navtb, "Back", self.navigate_back)
        self.add_toolbar_button(navtb, "Forward", self.navigate_forward)
        self.add_toolbar_button(navtb, "Reload", self.reload_page)
        self.add_toolbar_button(navtb, "Search", self.navigate_home)

        navtb.addSeparator()

        self.urlbar = QLineEdit()
        self.urlbar.returnPressed.connect(self.navigate_to_url)
        navtb.addWidget(self.urlbar)

        self.stop_btn = QAction("Stop", self)
        self.stop_btn.triggered.connect(self.stop_or_go)
        navtb.addAction(self.stop_btn)

        self.bookmarks_btn = QToolButton(self)
        self.bookmarks_btn.setText("Bookmarks")
        self.bookmarks_btn.setPopupMode(QToolButton.InstantPopup)
        navtb.addWidget(self.bookmarks_btn)

        self.add_toolbar_button(navtb, "Add Bookmark", self.add_bookmark)
        self.add_toolbar_button(navtb, "About", self.show_info)

    def add_toolbar_button(self, toolbar, name, handler):
        btn = QAction(name, self)
        btn.triggered.connect(handler)
        toolbar.addAction(btn)

    def init_statusbar(self):
        self.statusBar = self.statusBar()
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setVisible(False)
        self.cancel_button = QPushButton("Cancel", self)
        self.cancel_button.setVisible(False)
        self.cancel_button.clicked.connect(self.cancel_download)
        self.statusBar.addPermanentWidget(self.progress_bar)
        self.statusBar.addPermanentWidget(self.cancel_button)

    def set_initial_window_size(self):
        self.resize(800, 600)
        self.move(50, 50)

    def add_new_tab(self, qurl=None, label="Blank"):
        if qurl is None:
            qurl = QUrl('')
        browser = CustomWebEngineView(self, self)
        browser.setUrl(qurl)
        i = self.tabs.addTab(browser, label)
        self.tabs.setCurrentIndex(i)
        self.setup_browser_settings(browser)
        return browser

    def setup_browser_settings(self, browser):
        settings = browser.settings()
        settings.setAttribute(QWebEngineSettings.PluginsEnabled, False)
        settings.setAttribute(QWebEngineSettings.FullScreenSupportEnabled, False)
        settings.setAttribute(QWebEngineSettings.WebGLEnabled, True)
        settings.setAttribute(QWebEngineSettings.Accelerated2dCanvasEnabled, True)
        settings.setAttribute(QWebEngineSettings.AllowRunningInsecureContent, False)
        settings.setAttribute(QWebEngineSettings.AllowGeolocationOnInsecureOrigins, False)
        
        profile = browser.page().profile()
        profile.downloadRequested.connect(self.handle_download)
        browser.urlChanged.connect(lambda qurl, browser=browser: self.update_urlbar(qurl, browser))
        browser.loadStarted.connect(lambda: self.set_stop_button(browser, loading=True))
        browser.loadFinished.connect(lambda: self.set_stop_button(browser, loading=False))
        browser.loadFinished.connect(lambda _, i=self.tabs.indexOf(browser), browser=browser: self.set_tab_title(i, browser.page().title()))

    def navigate_back(self):
        if self.tabs.currentWidget():
            self.tabs.currentWidget().back()

    def navigate_forward(self):
        if self.tabs.currentWidget():
            self.tabs.currentWidget().forward()

    def reload_page(self):
        if self.tabs.currentWidget():
            self.tabs.currentWidget().reload()

    def stop_or_go(self):
        if self.stop_btn.text() == "Stop" and self.tabs.currentWidget():
            self.tabs.currentWidget().stop()
        else:
            self.navigate_to_url()

    def navigate_home(self):
        if self.tabs.currentWidget():
            self.tabs.currentWidget().setUrl(QUrl("https://duckduckgo.com"))

    def navigate_to_url(self):
        if self.tabs.currentWidget():
            q = QUrl(self.urlbar.text())
            if q.scheme() == "":
                q.setScheme("http")
            self.tabs.currentWidget().setUrl(q)

    def set_stop_button(self, browser, loading):
        if browser == self.tabs.currentWidget():
            if loading:
                self.stop_btn.setText("Stop")
                self.stop_btn.triggered.disconnect()
                self.stop_btn.triggered.connect(lambda: self.tabs.currentWidget().stop())
            else:
                self.stop_btn.setText("Go")
                self.stop_btn.triggered.disconnect()
                self.stop_btn.triggered.connect(self.navigate_to_url)

    def set_tab_title(self, index, title):
        max_length = 25
        if len(title) > max_length:
            title = title[:max_length] + "..."
        self.tabs.setTabText(index, title)

    def tab_open_doubleclick(self, i):
        if i == -1:
            self.add_new_tab()

    def current_tab_changed(self, i):
        current_widget = self.tabs.currentWidget()
        if current_widget:
            qurl = current_widget.url()
            self.update_urlbar(qurl, current_widget)
            self.update_title(current_widget)
            self.set_stop_button(current_widget, loading=False)

    def close_current_tab(self, i):
        if self.tabs.count() < 2:
            return
        self.tabs.removeTab(i)

    def update_title(self, browser):
        if browser == self.tabs.currentWidget():
            title = self.tabs.currentWidget().page().title()
            self.setWindowTitle(title)

    def update_urlbar(self, q, browser=None):
        if browser == self.tabs.currentWidget():
            self.urlbar.setText(q.toString())
            self.urlbar.setCursorPosition(0)

    def add_bookmark(self):
        current_url = self.tabs.currentWidget().url().toString()
        current_title = self.tabs.currentWidget().title()
        if not any(bm['url'] == current_url for bm in self.bookmarks):
            self.bookmarks.append({'name': current_title, 'url': current_url})
            self.settings.setValue("bookmarks", self.bookmarks)
            self.update_bookmarks_menu()

    def remove_bookmark(self, bookmark):
        self.bookmarks = [bm for bm in self.bookmarks if bm['url'] != bookmark['url']]
        self.settings.setValue("bookmarks", self.bookmarks)
        self.update_bookmarks_menu()

    def rename_bookmark(self, bookmark):
        dialog = RenameBookmarkDialog(bookmark['name'], bookmark['url'], self)
        if dialog.exec_() == QDialog.Accepted:
            new_name, new_url = dialog.get_data()
            bookmark['name'] = new_name
            bookmark['url'] = new_url
            self.settings.setValue("bookmarks", self.bookmarks)
            self.update_bookmarks_menu()

    def update_bookmarks_menu(self):
        menu = QMenu(self)
        for bookmark in self.bookmarks:
            bookmark_menu = QMenu(bookmark['name'], self)
            open_action = QAction("Open", self)
            open_action.triggered.connect(lambda checked, bookmark=bookmark: self.tabs.currentWidget().setUrl(QUrl(bookmark['url'])))
            remove_action = QAction("Remove", self)
            remove_action.triggered.connect(lambda checked, bookmark=bookmark: self.remove_bookmark(bookmark))
            rename_action = QAction("Rename", self)
            rename_action.triggered.connect(lambda checked, bookmark=bookmark: self.rename_bookmark(bookmark))
            bookmark_menu.addAction(open_action)
            bookmark_menu.addAction(rename_action)
            bookmark_menu.addAction(remove_action)
            menu.addMenu(bookmark_menu)
        self.bookmarks_btn.setMenu(menu)

    def show_info(self):
        py_version = platform.python_version()
        qt_version = QT_VERSION_STR
        program_version = "0.22"
        info_text = f"Breeze Version: {program_version}\nPython Version: {py_version}\nQt Version: {qt_version}"
        QMessageBox.information(self, "Information", info_text)

    def handle_download(self, download):
        suggested_filename = download.suggestedFileName()
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        file_path, _ = QFileDialog.getSaveFileName(self, "Save File", suggested_filename, options=options)
        if file_path:
            self.download_file_path = file_path
            download.setPath(file_path)
            download.accept()
            self.progress_bar.setVisible(True)
            self.cancel_button.setVisible(True)
            self.current_download = download
            download.downloadProgress.connect(self.update_progress_bar)
            download.finished.connect(self.download_finished)
            download.stateChanged.connect(self.download_state_changed)
        else:
            download.cancel()

    def update_progress_bar(self, bytes_received, bytes_total):
        if bytes_total > 0:
            progress = int((bytes_received / bytes_total) * 100)
            self.progress_bar.setValue(progress)

    def download_finished(self):
        if self.current_download and self.current_download.state() == QWebEngineDownloadItem.DownloadCompleted:
            self.progress_bar.setVisible(False)
            self.cancel_button.setVisible(False)
            if self.download_file_path and os.path.exists(self.download_file_path):
                QMessageBox.information(self, "Download Finished", f"File downloaded to: {self.download_file_path}")
            else:
                QMessageBox.critical(self, "Error", "Download failed.")
        self.reset_download_ui()

    def download_state_changed(self, state):
        if state == QWebEngineDownloadItem.DownloadCancelled:
            QMessageBox.information(self, "Download Cancelled", "The download has been cancelled.")
            self.reset_download_ui()
        elif state == QWebEngineDownloadItem.DownloadInterrupted:
            QMessageBox.critical(self, "Download Interrupted", "The download was interrupted.")
            self.reset_download_ui()
        elif state == QWebEngineDownloadItem.DownloadCompleted:
            self.download_finished()

    def cancel_download(self):
        if self.current_download:
            temp_path = self.current_download.path()
            self.current_download.cancel()
            self.current_download = None
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)
            self.reset_download_ui()

    def reset_download_ui(self):
        self.progress_bar.setVisible(False)
        self.cancel_button.setVisible(False)
        self.current_download = None

class CustomWebEngineView(QWebEngineView):
    def __init__(self, browser, parent=None):
        super().__init__(parent)
        self.browser = browser

    def createWindow(self, _type):
        return self.browser.add_new_tab()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("Breeze Browser")
    window = Browser()
    window.show()
    sys.exit(app.exec_())