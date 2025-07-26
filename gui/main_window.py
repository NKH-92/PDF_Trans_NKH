

import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
import json
import os
import sys
import webbrowser
from pathlib import Path
import re
import asyncio
import logging
from types import SimpleNamespace

# Import BabelDOC modules directly
from babeldoc.format.pdf.high_level import async_translate, init as babeldoc_init
from babeldoc.format.pdf.translation_config import TranslationConfig, WatermarkOutputMode
from babeldoc.translator.translator import OpenAITranslator, set_translate_rate_limiter
from babeldoc.docvision.doclayout import DocLayoutModel
from babeldoc.translator.gemini_bridge import start_gemini_bridge
from babeldoc.glossary import Glossary

# Configure logging to avoid conflicts with BabelDOC's internal logging
# and to direct logs to the GUI's log_textbox.
# We'll capture logs from BabelDOC and redirect them to our GUI's log_textbox.
class GUILogHandler(logging.Handler):
    def __init__(self, gui_instance):
        super().__init__()
        self.gui = gui_instance
        self.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))

    def emit(self, record):
        msg = self.format(record)
        self.gui.root.after(0, self.gui.update_log, msg + "\n")

# PyInstaller로 빌드된 .exe 환경과 일반 .py 실행 환경 모두에서 파일 경로를 올바르게 찾기 위한 함수
def get_base_path():
    if getattr(sys, 'frozen', False):
        # Set TIKTOKEN_CACHE_DIR for PyInstaller bundled app
        cache_dir = Path(sys._MEIPASS)
        os.makedirs(cache_dir, exist_ok=True)
        os.environ["TIKTOKEN_CACHE_DIR"] = str(cache_dir)
        return Path(sys._MEIPASS)
    return Path(__file__).parent.parent

BASE_PATH = get_base_path()
CONFIG_FILE = BASE_PATH / "config.json"
APP_NAME = "PDF 번역 (남광현_Test Ver)"

class PDFTranslatorGUI:
    def __init__(self):
        # --- 기본 설정 ---
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")
        
        self.root = ctk.CTk()
        self.root.title(APP_NAME)
        self.root.geometry("850x750")
        self.root.minsize(800, 700)

        # --- 설정 로드 ---
        self.config = self.load_config()

        # --- UI 상태 변수 선언 ---
        self.file_path = ctk.StringVar()
        self.target_lang = ctk.StringVar(value="ko")
        self.output_format = ctk.StringVar(value="both")
        self.api_key = ctk.StringVar()
        self.ai_model = ctk.StringVar(value=self.config["supported_models"][1])

        self.is_translating = False
        
        # --- 위젯 생성 ---
        self.create_widgets()

        # --- 로깅 설정 ---
        self.gui_log_handler = GUILogHandler(self)
        # Remove existing handlers to prevent duplicate logs
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
        logging.basicConfig(level=logging.INFO, handlers=[self.gui_log_handler])
        logging.getLogger("httpx").setLevel(logging.CRITICAL)
        logging.getLogger("openai").setLevel(logging.CRITICAL)
        logging.getLogger("httpcore").setLevel(logging.CRITICAL)
        logging.getLogger("http11").setLevel(logging.CRITICAL)
        # Initialize BabelDOC's internal components
        babeldoc_init()


    def load_config(self):
        """config.json 파일에서 설정을 로드합니다."""
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            messagebox.showerror("치명적 오류", f"설정 파일({CONFIG_FILE})을 찾을 수 없습니다. 프로그램을 종료합니다.")
            sys.exit(1)
        except json.JSONDecodeError:
            messagebox.showerror("치명적 오류", f"설정 파일({CONFIG_FILE})의 형식이 올바르지 않습니다. 프로그램을 종료합니다.")
            sys.exit(1)

    def create_widgets(self):
        """애플리케이션의 모든 UI 요소를 생성하고 배치합니다."""
        main_frame = ctk.CTkFrame(self.root)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(5, weight=1)

        # 1. 제목
        ctk.CTkLabel(main_frame, text="🎯 PDF 번역 (남광현_Test Ver)", font=ctk.CTkFont(size=24, weight="bold")).grid(row=0, column=0, pady=(10, 20))

        # 2. 파일 선택
        self.create_file_selection(main_frame).grid(row=1, column=0, sticky="ew", padx=20, pady=10)
        
        # 3. 설정 (언어, 출력, 모델)
        self.create_settings_frame(main_frame).grid(row=2, column=0, sticky="ew", padx=20, pady=10)

        # 4. API 키 입력
        self.create_api_key_input(main_frame).grid(row=3, column=0, sticky="ew", padx=20, pady=10)

        # 5. 번역 버튼
        self.translate_btn = ctk.CTkButton(main_frame, text="🚀 번역 시작하기", command=self.start_translation, height=50, font=ctk.CTkFont(size=16, weight="bold"))
        self.translate_btn.grid(row=4, column=0, pady=20, padx=20, sticky="ew")

        # 6. 진행 상황 및 로그
        self.create_progress_section(main_frame).grid(row=5, column=0, sticky="nsew", padx=20, pady=10)

        # 7. 푸터 (프로그램명 표시)
        footer_label = ctk.CTkLabel(main_frame, text=APP_NAME, font=ctk.CTkFont(size=10), text_color="gray")
        footer_label.grid(row=6, column=0, pady=(10, 0), sticky="e")

    def create_section_frame(self, parent, title):
        frame = ctk.CTkFrame(parent)
        ctk.CTkLabel(frame, text=title, font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(10, 5), anchor="w", padx=20)
        return frame

    def create_file_selection(self, parent):
        frame = self.create_section_frame(parent, "📂 1. 번역할 PDF 파일 선택")
        file_frame = ctk.CTkFrame(frame, fg_color="transparent")
        file_frame.pack(fill="x", padx=20, pady=(5, 15))
        file_frame.grid_columnconfigure(0, weight=1)
        file_entry = ctk.CTkEntry(file_frame, textvariable=self.file_path, placeholder_text="여기를 클릭하여 파일을 선택하세요...")
        file_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        browse_btn = ctk.CTkButton(file_frame, text="찾아보기", command=self.browse_file, width=100)
        browse_btn.grid(row=0, column=1)
        return frame

    def create_settings_frame(self, parent):
        frame = self.create_section_frame(parent, "⚙️ 2. 번역 옵션 설정")
        
        content_frame = ctk.CTkFrame(frame, fg_color="transparent")
        content_frame.pack(fill="x", padx=0, pady=0, expand=True)
        content_frame.columnconfigure((0,1), weight=1)

        left_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        left_frame.grid(row=0, column=0, padx=20, pady=5, sticky="ew")
        ctk.CTkLabel(left_frame, text="번역 언어 (대상)").pack(anchor="w")
        ctk.CTkComboBox(left_frame, values=["ko (한국어)", "en (영어)", "ja (일본어)", "zh (중국어)"], variable=self.target_lang).pack(fill="x")
        ctk.CTkLabel(left_frame, text="출력 형식").pack(anchor="w", pady=(10,0))
        ctk.CTkRadioButton(left_frame, text="번역본만", variable=self.output_format, value="mono").pack(anchor="w")
        ctk.CTkRadioButton(left_frame, text="이중언어본만", variable=self.output_format, value="dual").pack(anchor="w")
        ctk.CTkRadioButton(left_frame, text="둘 다 생성", variable=self.output_format, value="both").pack(anchor="w")
        
        right_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        right_frame.grid(row=0, column=1, padx=20, pady=5, sticky="ew")
        ctk.CTkLabel(right_frame, text="AI 모델 선택").pack(anchor="w")
        for model in self.config["supported_models"]:
            desc = self.config["model_descriptions"].get(model, "")
            ctk.CTkRadioButton(right_frame, text=f"{model}\n({desc})", variable=self.ai_model, value=model).pack(anchor="w", pady=2)
            
        return frame

    def create_api_key_input(self, parent):
        frame = self.create_section_frame(parent, "🔑 3. Google Gemini API 키")
        
        content_frame = ctk.CTkFrame(frame, fg_color="transparent")
        content_frame.pack(fill="x", padx=0, pady=0, expand=True)
        content_frame.grid_columnconfigure(0, weight=1)

        api_entry = ctk.CTkEntry(content_frame, textvariable=self.api_key, placeholder_text="API 키를 여기에 붙여넣으세요...", show="*")
        api_entry.grid(row=0, column=0, padx=20, pady=5, sticky="ew")
        help_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        help_frame.grid(row=0, column=1, padx=(0, 20))
        help_btn = ctk.CTkButton(help_frame, text="API 키 발급받기", command=self.open_api_key_url, width=120)
        help_btn.pack()
        return frame

    def create_progress_section(self, parent):
        frame = self.create_section_frame(parent, "🔄 진행 상황 및 로그")
        
        content_frame = ctk.CTkFrame(frame, fg_color="transparent")
        content_frame.pack(fill="both", padx=0, pady=0, expand=True)
        content_frame.grid_columnconfigure(0, weight=1)
        content_frame.grid_rowconfigure(1, weight=1)

        self.progress = ctk.CTkProgressBar(content_frame)
        self.progress.grid(row=0, column=0, sticky="ew", padx=20, pady=5)
        self.progress.set(0)
        self.log_textbox = ctk.CTkTextbox(content_frame, state="disabled", wrap="word", font=ctk.CTkFont(family="Courier New", size=12))
        self.log_textbox.grid(row=1, column=0, sticky="nsew", padx=20, pady=(5, 15))
        return frame

    def browse_file(self):
        if self.is_translating: return
        file_path = filedialog.askopenfilename(title="번역할 PDF 파일을 선택하세요", filetypes=[("PDF files", "*.pdf")])
        if file_path:
            self.file_path.set(file_path)

    def open_api_key_url(self):
        webbrowser.open_new_tab(self.config["api_key_help_url"])

    def update_log(self, text):
        """백그라운드 스레드에서 UI를 안전하게 업데이트하기 위한 함수입니다."""
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", text)
        self.log_textbox.see("end")
        self.log_textbox.configure(state="disabled")

    def update_progress(self, value):
        """스레드로부터 받은 값으로 프로그레스 바를 업데이트합니다."""
        self.progress.set(value)

    def set_ui_state(self, is_active):
        """번역 중/완료 시 UI 상태를 변경하여 사용자 실수를 방지합니다."""
        self.is_translating = is_active
        state = "disabled" if is_active else "normal"
        self.translate_btn.configure(state=state, text="번역 중..." if is_active else "🚀 번역 시작하기")
        for widget in self.root.winfo_children():
            if isinstance(widget, ctk.CTkFrame):
                for child in widget.winfo_children():
                    if child != self.translate_btn and child.master != self.progress.master:
                        try:
                            child.configure(state=state)
                        except:
                             pass

    def start_translation(self):
        """'번역 시작' 버튼 클릭 시 호출되는 메인 이벤트 핸들러입니다."""
        if not self.file_path.get():
            messagebox.showerror("입력 오류", "번역할 PDF 파일을 선택해주세요.")
            return
        if not self.api_key.get():
            messagebox.showerror("입력 오류", "Gemini API 키를 입력해주세요.")
            return
        self.set_ui_state(True)
        self.progress.set(0)
        self.log_textbox.configure(state="normal")
        self.log_textbox.delete("1.0", "end")
        self.log_textbox.configure(state="disabled")
        self.update_log("번역 프로세스를 시작합니다...\n")
        thread = threading.Thread(target=lambda: asyncio.run(self.run_translation_process()))
        thread.daemon = True
        thread.start()

    async def run_translation_process(self):
        """실제 번역 로직을 현재 프로세스 내에서 실행합니다."""
        try:
            # Create a SimpleNamespace object to mimic the argparse.args object
            args = SimpleNamespace()
            args.files = [self.file_path.get()]
            args.lang_out = self.target_lang.get().split()[0]
            args.gemini = True
            args.gemini_model = self.ai_model.get()
            args.gemini_api_key = self.api_key.get()
            args.watermark_output_mode = "no_watermark"
            args.report_interval = 1.0 # Float value
            args.no_dual = False
            args.no_mono = False
            args.debug = False # Set to True for more verbose logging
            args.qps = 0.25 # Default QPS for Gemini free tier
            args.gemini_qps = args.qps # Ensure gemini_qps is also set
            args.pages = None
            args.min_text_length = 5
            args.output = None # Let BabelDOC decide output path
            args.formular_font_pattern = None
            args.formular_char_pattern = None
            args.split_short_lines = False
            args.short_line_split_factor = 0.8
            args.skip_clean = False
            args.dual_translate_first = False
            args.disable_rich_text_translate = False
            args.enhance_compatibility = False
            args.use_alternating_pages_dual = False
            args.max_pages_per_part = None
            args.translate_table_text = False
            args.show_char_box = False
            args.skip_scanned_detection = False
            args.ocr_workaround = False
            args.custom_system_prompt = None
            args.working_dir = None
            args.add_formula_placehold_hint = False
            args.glossary_files = None
            args.pool_max_workers = None
            args.auto_extract_glossary = True
            args.auto_enable_ocr_workaround = False
            args.primary_font_family = None
            args.only_include_translated_page = False
            args.save_auto_extracted_glossary = False
            args.openai = False # Will be set to True if gemini bridge starts
            args.openai_model = None
            args.openai_base_url = None
            args.openai_api_key = None

            if self.output_format.get() == "mono":
                args.no_dual = True
            elif self.output_format.get() == "dual":
                args.no_mono = True

            self.root.after(0, self.update_log, f"선택된 파일: {args.files[0]}\n")
            self.root.after(0, self.update_log, f"대상 언어: {args.lang_out}\n")
            self.root.after(0, self.update_log, f"AI 모델: {args.gemini_model}\n")
            self.root.after(0, self.update_log, f"출력 형식: {self.output_format.get()}\n\n")

            # --- Gemini 브릿지 실행 로직 (babeldoc.main.py에서 가져옴) ---
            if args.gemini:
                self.root.after(0, self.update_log, "Gemini 모드가 활성화되었습니다. 로컬 브릿지 서버를 시작합니다...\n")
                
                if not args.gemini_api_key:
                    self.root.after(0, lambda: messagebox.showerror("오류", "Gemini API 키가 필요합니다."))
                    raise ValueError("Gemini API key is required.")
                
                try:
                    base_url, port = start_gemini_bridge(
                        api_key=args.gemini_api_key, 
                        model=args.gemini_model, 
                        qps=args.qps
                    )
                    
                    args.openai = True
                    args.openai_base_url = base_url
                    args.openai_api_key = "DUMMY_KEY_FOR_BRIDGE"
                    args.openai_model = args.gemini_model
                    
                    
                    self.root.after(0, self.update_log, f"✅ Gemini 브릿지 서버가 {base_url} 에서 성공적으로 시작되었습니다.\n")
                    self.root.after(0, self.update_log, "BabelDOC이 이 로컬 서버를 통해 번역을 진행합니다.\n")

                except Exception as e:
                    self.root.after(0, self.update_log, f"❌ Gemini 브릿지 서버 시작에 실패했습니다: {e}\n")
                    self.root.after(0, lambda: messagebox.showerror("오류", f"Gemini 브릿지 서버 시작 실패: {e}"))
                    raise

            # Instantiate translator
            if args.openai: # Now args.openai should be True if Gemini bridge started
                translator = OpenAITranslator(
                    lang_in="en", # BabelDOC's default, can be made configurable if needed
                    lang_out=args.lang_out,
                    model=args.openai_model,
                    base_url=args.openai_base_url,
                    api_key=args.openai_api_key,
                    ignore_cache=False, # Can be made configurable
                )
            else:
                self.root.after(0, lambda: messagebox.showerror("오류", "번역 서비스를 선택하거나 Gemini 브릿지 시작에 실패했습니다."))
                raise ValueError("No translation service selected or Gemini bridge failed.")

            # Set translation rate limit
            set_translate_rate_limiter(args.qps)

            # Initialize document layout model
            doc_layout_model = DocLayoutModel.load_onnx()

            # Load glossaries (simplified for GUI, assuming no glossary files for now)
            loaded_glossaries = []
            if args.glossary_files:
                self.root.after(0, self.update_log, "경고: GUI에서는 용어집 파일 로딩이 지원되지 않습니다.\n")

            watermark_output_mode = WatermarkOutputMode.NoWatermark # Default from GUI
            if args.watermark_output_mode == "both":
                watermark_output_mode = WatermarkOutputMode.Both
            elif args.watermark_output_mode == "watermarked":
                watermark_output_mode = WatermarkOutputMode.Watermarked
            elif args.watermark_output_mode == "no_watermark":
                watermark_output_mode = WatermarkOutputMode.NoWatermark

            # Create TranslationConfig object
            config = TranslationConfig(
                input_file=args.files[0],
                font=None,
                pages=args.pages,
                output_dir=args.output,
                translator=translator,
                debug=args.debug,
                lang_in="en", # BabelDOC's default, can be made configurable if needed
                lang_out=args.lang_out,
                no_dual=args.no_dual,
                no_mono=args.no_mono,
                qps=args.qps,
                formular_font_pattern=args.formular_font_pattern,
                formular_char_pattern=args.formular_char_pattern,
                split_short_lines=args.split_short_lines,
                short_line_split_factor=args.short_line_split_factor,
                doc_layout_model=doc_layout_model,
                skip_clean=args.skip_clean,
                dual_translate_first=args.dual_translate_first,
                disable_rich_text_translate=args.disable_rich_text_translate,
                enhance_compatibility=args.enhance_compatibility,
                use_alternating_pages_dual=args.use_alternating_pages_dual,
                report_interval=args.report_interval,
                min_text_length=args.min_text_length,
                watermark_output_mode=watermark_output_mode,
                split_strategy=None, # Not exposed in GUI
                table_model=None, # Not exposed in GUI
                show_char_box=args.show_char_box,
                skip_scanned_detection=args.skip_scanned_detection,
                ocr_workaround=args.ocr_workaround,
                custom_system_prompt=args.custom_system_prompt,
                working_dir=args.working_dir,
                add_formula_placehold_hint=args.add_formula_placehold_hint,
                glossaries=loaded_glossaries,
                pool_max_workers=args.pool_max_workers,
                auto_extract_glossary=args.auto_extract_glossary,
                auto_enable_ocr_workaround=args.auto_enable_ocr_workaround,
                primary_font_family=args.primary_font_family,
                only_include_translated_page=args.only_include_translated_page,
                save_auto_extracted_glossary=args.save_auto_extracted_glossary,
            )

            # Progress handler for GUI
            def gui_progress_handler(event):
                if event["type"] == "progress_update":
                    progress_percent = event["overall_progress"]
                    self.root.after(0, self.update_progress, progress_percent / 100.0)
                    self.root.after(0, self.update_log, f"Progress: {progress_percent:.1f}% - {event['stage']} ({event['stage_current']}/{event['stage_total']})\n")
                elif event["type"] == "finish":
                    result = event["translate_result"]
                    self.root.after(0, self.update_log, f"\n🎉 번역이 성공적으로 완료되었습니다! 결과: {result}\n")
                    self.root.after(0, lambda: self.progress.set(1.0))
                    self.root.after(0, lambda: messagebox.showinfo("성공", "PDF 번역이 완료되었습니다!"))
                elif event["type"] == "error":
                    error_msg = f"❌ 오류: {event['error']}\n"
                    self.root.after(0, self.update_log, error_msg)
                    self.root.after(0, lambda: messagebox.showerror("오류", f"번역 중 오류가 발생했습니다: {event['error']}"))

            # Start translation
            self.root.after(0, self.update_log, "번역을 시작합니다...\n")
            async for event in async_translate(config):
                gui_progress_handler(event)

        except Exception as e:
            error_msg = f"\n❌ 치명적 오류 발생: {e}\n"
            self.root.after(0, self.update_log, error_msg)
            self.root.after(0, lambda: messagebox.showerror("치명적 오류", str(e)))
        finally:
            self.root.after(0, self.set_ui_state, False)

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = PDFTranslatorGUI()
    app.run()
