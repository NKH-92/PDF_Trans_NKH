## PDF 번역기 (남광현_Test Ver) 매뉴얼

### 1. 프로그램 개요

이 프로그램은 Python과 CustomTkinter를 사용하여 개발된 PDF 번역 GUI 애플리케이션입니다. Google Gemini AI 모델을 활용하여 PDF 문서를 한국어, 영어, 일본어, 중국어 등으로 번역하고, 번역된 결과를 단일 언어 PDF 또는 원본과 번역본이 함께 있는 이중 언어 PDF로 출력합니다. PyInstaller를 통해 포터블 실행 파일(EXE)로 빌드되어 별도의 Python 환경 설정 없이 실행 가능합니다.

### 2. 프로그램 작동 방식

1.  **GUI 실행:** `dist` 폴더 내의 `PDF번역기_남광현_Test.exe` 파일을 실행하면 GUI 창이 나타납니다.
2.  **PDF 파일 선택:** "번역할 PDF 파일 선택" 섹션에서 번역하고자 하는 PDF 파일을 선택합니다.
3.  **번역 옵션 설정:**
    *   **번역 언어 (대상):** 번역될 언어를 선택합니다.
    *   **AI 모델 선택:** 번역에 사용할 Gemini AI 모델을 선택합니다.
    *   **출력 형식:** 번역본만 (`MONO`) 또는 이중 언어본 (`DUAL`) 중 하나를 선택하거나 둘 다 생성할 수 있습니다.
4.  **Google Gemini API 키 입력:** Google Gemini API 키를 입력합니다. API 키 발급 링크도 제공됩니다.
5.  **번역 시작:** "번역 시작하기" 버튼을 클릭하면 번역 프로세스가 시작됩니다.
6.  **번역 프로세스:**
    *   프로그램은 내부적으로 BabelDOC 라이브러리를 사용하여 PDF를 파싱하고, 텍스트를 추출하며, 레이아웃을 분석합니다.
    *   입력된 Gemini API 키를 사용하여 로컬 브릿지 서버를 시작하고, 이 서버를 통해 Gemini 모델과 통신하여 텍스트를 번역합니다.
    *   번역된 텍스트는 원본 PDF의 레이아웃을 유지하며 새로운 PDF로 재구성됩니다.
    *   폰트 서브셋팅 및 PDF 저장 과정은 서브프로세스를 통해 처리됩니다.
7.  **결과 출력:** 번역이 완료되면 `dist` 폴더 내에 번역된 PDF 파일이 생성됩니다. 파일명은 `[원본 파일명]_NKH Trans_MONO.pdf` 또는 `[원본 파일명]_NKH Trans_DUAL.pdf` 형식으로 저장됩니다.
8.  **로그 및 진행 상황:** GUI 하단의 로그 창에서 번역 진행 상황과 발생한 메시지(정보, 경고, 오류)를 실시간으로 확인할 수 있습니다.

### 3. 중요 파일 및 역할

*   **`build_exe.py`**:
    *   **역할:** PyInstaller를 사용하여 Python 스크립트와 모든 의존성을 하나의 포터블 실행 파일(`PDF번역기_남광현_Test.exe`)로 묶는 빌드 스크립트입니다.
    *   **주요 설정:**
        *   `--onefile`: 모든 것을 하나의 EXE 파일로 만듭니다.
        *   `--windowed`: GUI 애플리케이션 실행 시 콘솔 창이 뜨지 않도록 합니다.
        *   `--icon assets/icon.ico`: 애플리케이션 아이콘을 지정합니다.
        *   `--add-data`: BabelDOC의 `assets` 폴더와 `config.json` 파일을 EXE 내부에 포함시킵니다.
        *   `--hidden-import`: PyInstaller가 자동으로 감지하지 못하는 동적 임포트 라이브러리들을 명시적으로 추가합니다 (예: `google.generativeai`, `customtkinter`, `babeldoc` 등).
*   **`gui/main_window.py`**:
    *   **역할:** 프로그램의 메인 GUI 로직을 담당하는 파일입니다. 사용자 인터페이스(UI)를 생성하고, 사용자 입력을 처리하며, 번역 프로세스를 시작하고 진행 상황을 업데이트합니다.
    *   **주요 기능:**
        *   `PDFTranslatorGUI` 클래스: GUI의 모든 위젯을 초기화하고 배치합니다.
        *   `start_translation` 함수: "번역 시작하기" 버튼 클릭 시 호출되며, 번역 로직을 비동기적으로 실행합니다.
        *   `run_translation_process` 함수: 실제 BabelDOC 번역 함수를 호출하고, Gemini 브릿지 서버를 시작하는 로직을 포함합니다.
        *   `update_log`, `update_progress`: GUI의 로그 창과 진행률 바를 업데이트합니다.
        *   `APP_NAME` 변수: GUI 창의 제목과 푸터에 표시되는 프로그램 이름을 정의합니다.
*   **`BabelDOC/babeldoc/format/pdf/document_il/backend/pdf_creater.py`**:
    *   **역할:** PDF 문서 생성 및 폰트 처리, 서브프로세스 관리를 담당하는 BabelDOC 라이브러리 내부 파일입니다.
    *   **주요 수정 사항:**
        *   `subset_fonts_in_subprocess` 및 `save_pdf_with_timeout` 함수에서 `subprocess.Popen` 객체의 `start()` 메서드 호출을 제거했습니다. `Popen`은 생성 시 바로 시작됩니다.
        *   `process.is_alive()` 대신 `process.poll() is None`을 사용하여 서브프로세스 생존 여부를 확인하도록 수정했습니다.
        *   `process.join()` 대신 `process.wait()`를 사용하여 서브프로세스 종료를 기다리도록 수정했습니다.
        *   `write` 함수 내에서 출력 파일명 생성 로직을 `f"{basename}_NKH Trans_MONO.pdf"` 및 `f"{basename}_NKH Trans_DUAL.pdf"` 형식으로 변경했습니다.
*   **`config.json`**:
    *   **역할:** 프로그램의 설정 정보를 담고 있는 JSON 파일입니다.
    *   **주요 내용:** `supported_models` (지원되는 AI 모델 목록), `model_descriptions` (모델 설명), `api_key_help_url` (API 키 발급 도움말 URL) 등이 포함됩니다.
*   **`assets/icon.ico`**:
    *   **역할:** 빌드된 EXE 파일의 아이콘으로 사용되는 이미지 파일입니다.
*   **`requirements.txt`**:
    *   **역할:** 프로젝트에 필요한 Python 라이브러리 및 그 버전을 명시하는 파일입니다. `pip install -r requirements.txt` 명령으로 모든 의존성을 설치할 수 있습니다.
*   **`dist/`**:
    *   **역할:** PyInstaller 빌드 결과물(포터블 EXE 파일 및 관련 데이터)이 저장되는 폴더입니다. 번역된 PDF 파일도 이 폴더에 저장됩니다.

### 4. 유지보수 및 문제 해결

#### 4.1. EXE 파일 재빌드

프로그램 코드(`build_exe.py`, `gui/main_window.py`, `BabelDOC` 내부 파일 등)를 수정한 경우, 변경 사항을 반영하려면 EXE 파일을 다시 빌드해야 합니다.

**재빌드 절차:**

1.  **실행 중인 EXE 종료:** `dist` 폴더 내의 `PDF번역기_남광현_Test.exe` 파일이 실행 중이라면, **반드시 작업 관리자(Ctrl+Shift+Esc)에서 해당 프로세스를 종료**해야 합니다. 그렇지 않으면 `PermissionError`가 발생하여 빌드가 실패합니다.
2.  **`dist` 및 `build` 폴더 수동 삭제 (선택 사항이지만 권장):** 파일 탐색기에서 `D:\Gemini_cli\dist` 폴더와 `D:\Gemini_cli\build` 폴더를 수동으로 삭제합니다. `build_exe.py` 스크립트 내부에 삭제 로직이 포함되어 있지만, 간혹 권한 문제로 실패할 수 있으므로 수동 삭제가 가장 확실합니다.
3.  **`build_exe.py` 실행:** 명령 프롬프트(CMD) 또는 PowerShell을 열고 `D:\Gemini_cli` 경로로 이동한 후 다음 명령어를 실행합니다.
    ```bash
    python build_exe.py
    ```
4.  **빌드 확인:** 빌드가 성공적으로 완료되면 `dist` 폴더에 새로운 `PDF번역기_남광현_Test.exe` 파일이 생성됩니다.

#### 4.2. 번역 관련 문제 해결

*   **로그 확인:** 번역 중 오류가 발생하면 GUI 하단의 로그 창을 가장 먼저 확인합니다. 상세한 오류 메시지가 출력됩니다.
*   **`AttributeError: 'Popen' object has no attribute 'start'` 또는 `'is_alive'` 또는 `'join'`:**
    *   **원인:** `babeldoc\format\pdf\document_il\backend\pdf_creater.py` 파일에서 `subprocess.Popen` 객체의 잘못된 메서드를 호출했을 때 발생합니다.
    *   **해결:** 해당 파일에서 `process.start()`는 제거하고, `process.is_alive()`는 `process.poll() is None`으로, `process.join()`은 `process.wait()`로 변경되었는지 확인합니다. (이 매뉴얼 작성 시점에 이미 수정되었습니다.)
*   **`Gemini 브릿지 서버 시작 실패`:**
    *   **원인:** Gemini API 키가 유효하지 않거나, 네트워크 문제, 또는 Gemini 서비스 자체의 문제일 수 있습니다.
    *   **해결:** API 키를 다시 확인하고, 인터넷 연결 상태를 점검하며, `config.json`의 `api_key_help_url`을 통해 API 키 발급 가이드를 참조합니다.
*   **`ModuleNotFoundError` (EXE 실행 시):**
    *   **원인:** PyInstaller가 필요한 라이브러리를 EXE 파일에 제대로 포함하지 못했을 때 발생합니다.
    *   **해결:** `build_exe.py` 파일의 `hidden_imports` 리스트에 누락된 라이브러리 이름을 추가하고 재빌드합니다.
*   **번역 품질 문제:**
    *   **원인:** AI 모델의 한계, 원본 PDF의 복잡한 레이아웃, 특수 문자 처리 문제 등.
    *   **해결:** 다른 AI 모델을 시도하거나, `babeldoc` 라이브러리의 추가 설정(예: `ocr_workaround`, `split_short_lines` 등)을 `gui/main_window.py`의 `run_translation_process` 함수 내 `args` 객체에 추가하여 테스트해 볼 수 있습니다.

#### 4.3. 의존성 업데이트

프로젝트의 Python 라이브러리 버전을 업데이트해야 할 경우:

1.  **`requirements.txt` 업데이트:** 필요한 라이브러리 버전을 `requirements.txt` 파일에 직접 수정합니다.
2.  **재설치:** 다음 명령어를 사용하여 의존성을 재설치합니다.
    ```bash
    pip install -r requirements.txt
    ```
3.  **EXE 재빌드:** 변경된 라이브러리가 EXE 파일에 반영되도록 `build_exe.py`를 사용하여 EXE 파일을 재빌드합니다.

#### 4.4. 기능 수정 및 확장

*   **GUI 요소 변경:** `gui/main_window.py` 파일의 `create_widgets` 및 관련 `create_..._frame` 함수들을 수정하여 UI 레이아웃, 텍스트, 버튼 등을 변경할 수 있습니다.
*   **번역 로직 변경:** `gui/main_window.py`의 `run_translation_process` 함수 내 `args` 객체에 `TranslationConfig`에 전달되는 인자들을 수정하여 번역 동작을 제어할 수 있습니다.
*   **새로운 AI 모델 추가:** `config.json` 파일의 `supported_models` 리스트와 `model_descriptions` 딕셔너리에 새로운 모델 정보를 추가하고, `gui/main_window.py`의 `create_settings_frame`에서 해당 모델이 UI에 표시되도록 합니다. 실제 번역 로직(`OpenAITranslator` 또는 `start_gemini_bridge`)이 해당 모델을 지원하는지 확인해야 합니다.
*   **출력 파일명 변경:** `babeldoc\format\pdf\document_il\backend\pdf_creater.py` 파일의 `write` 함수 내 `mono_out_path`와 `dual_out_path` 생성 부분을 수정합니다.

### 5. 향후 유지보수 팁

*   **버전 관리:** Git과 같은 버전 관리 시스템을 사용하여 코드 변경 이력을 관리하는 것이 좋습니다.
*   **주석:** 코드에 충분한 주석을 달아 다른 개발자(또는 미래의 자신)가 코드를 이해하기 쉽도록 합니다.
*   **테스트:** 중요한 기능에 대한 단위 테스트를 작성하여 코드 변경 시 회귀를 방지합니다.
*   **BabelDOC 업데이트:** BabelDOC 라이브러리 자체의 업데이트가 있을 경우, `requirements.txt`를 통해 버전을 업데이트하고 변경 사항을 확인하여 프로그램에 반영해야 할 수 있습니다.
*   **PyInstaller 업데이트:** PyInstaller 버전이 변경될 경우, 빌드 스크립트(`build_exe.py`)의 호환성을 확인해야 할 수 있습니다.
