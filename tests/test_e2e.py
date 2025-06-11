import pytest
from selenium.common.exceptions import TimeoutException, NoSuchElementException


class FlaskAppRunner:
    """Clase para manejar la ejecución de la aplicación Flask en las pruebas"""

    def __init__(self, port=5555):
        self.port = port
        self.process = None
        self.base_url = f"http://localhost:{port}"

    def start(self):
        """Inicia la aplicación Flask en un proceso separado"""
        print(f"[E2E] Iniciando Flask en puerto {self.port}...")

        # Configurar entorno
        env = os.environ.copy()
        env["FLASK_ENV"] = "testing"
        env["PORT"] = str(self.port)
        env["HOST"] = "127.0.0.1"
        # Configurar encoding para Windows
        env["PYTHONIOENCODING"] = "utf-8"

        # Cambiar al directorio del proyecto
        project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        try:
            # Iniciar Flask
            self.process = subprocess.Popen(
                [sys.executable, "app.py"],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=project_dir,
                text=True,
            )

            # Esperar a que la aplicación esté lista
            max_attempts = 30
            for attempt in range(max_attempts):
                if self.process.poll() is not None:
                    # El proceso terminó, leer la salida de error
                    stdout, stderr = self.process.communicate()
                    raise Exception(
                        f"Flask app failed to start.\nSTDOUT: {stdout}\nSTDERR: {stderr}"
                    )

                try:
                    response = requests.get(f"{self.base_url}/", timeout=5)
                    if response.status_code == 200:
                        print(f"[E2E] Flask iniciado correctamente en {self.base_url}")
                        return
                except requests.exceptions.RequestException:
                    pass

                print(f"[E2E] Esperando Flask... intento {attempt + 1}/{max_attempts}")
                time.sleep(2)

            raise Exception("Flask app no respondió después de 60 segundos")

        except Exception as e:
            if self.process:
                self.process.terminate()
            raise Exception(f"Error iniciando Flask: {e}")

    def stop(self):
        """Detiene la aplicación Flask"""
        if self.process:
            print("[E2E] Deteniendo Flask...")
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                print("[E2E] Forzando terminación de Flask...")
                self.process.kill()
                self.process.wait()
            self.process = None


@pytest.fixture(scope="session")
def flask_app():
    """Fixture para iniciar y detener la aplicación Flask"""
    app_runner = FlaskAppRunner()

    try:
        app_runner.start()
        yield app_runner
    finally:
        app_runner.stop()


@pytest.fixture(scope="session")
def driver():
    """Fixture para configurar el driver de Selenium"""
    chrome_options = Options()

    # Configuración para CI/CD y desarrollo local
    chrome_options.add_argument("--headless")  # Ejecutar sin interfaz gráfica
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-web-security")
    chrome_options.add_argument("--allow-running-insecure-content")
    chrome_options.add_argument("--disable-features=VizDisplayCompositor")
    chrome_options.add_argument("--disable-background-networking")
    chrome_options.add_argument("--disable-sync")
    chrome_options.add_argument("--disable-translate")
    chrome_options.add_argument("--disable-ipc-flooding-protection")

    # Configuración adicional para Windows
    if os.name == "nt":
        chrome_options.add_argument("--disable-background-timer-throttling")
        chrome_options.add_argument("--disable-backgrounding-occluded-windows")
        chrome_options.add_argument("--disable-renderer-backgrounding")

    try:
        # Usar webdriver-manager para gestionar ChromeDriver automáticamente
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)

        # Configurar timeouts más largos
        driver.implicitly_wait(15)
        driver.set_page_load_timeout(30)

        print("Chrome WebDriver iniciado correctamente")
        yield driver

    except Exception as e:
        print(f"Error iniciando Chrome WebDriver: {e}")
        raise
    finally:
        try:
            driver.quit()
            print("Chrome WebDriver cerrado")
        except:
            pass


class TestTaskListE2E:
    """Suite de pruebas End-to-End para la aplicación de lista de tareas"""

    def wait_for_page_load(self, driver):
        """Espera a que la página esté completamente cargada"""
        WebDriverWait(driver, 15).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        time.sleep(1)  # Pausa adicional para asegurar renderizado

    def safe_find_element(self, driver, selector, timeout=10):
        """Encuentra un elemento de forma segura con retry"""
        try:
            element = WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
            return element
        except TimeoutException:
            print(f"[WARNING] No se encontró elemento: {selector}")
            return None

    def safe_click(self, driver, element):
        """Click seguro con scroll si es necesario"""
        try:
            # Scroll al elemento
            driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", element
            )
            time.sleep(0.5)

            # Esperar que sea clickeable
            WebDriverWait(driver, 10).until(EC.element_to_be_clickable(element))
            element.click()
            return True
        except Exception as e:
            print(f"[WARNING] Error en click: {e}")
            # Intentar click con JavaScript
            try:
                driver.execute_script("arguments[0].click();", element)
                return True
            except:
                return False

    def test_page_loads_successfully(self, driver, flask_app):
        """Prueba que la página principal carga correctamente"""
        print(f"[TEST] Probando carga de página en {flask_app.base_url}")

        # Verificar que Flask está respondiendo
        response = requests.get(flask_app.base_url, timeout=10)
        assert (
            response.status_code == 200
        ), f"Flask no responde correctamente: {response.status_code}"

        driver.get(flask_app.base_url)
        self.wait_for_page_load(driver)

        # Verificar que el título es correcto
        assert "Lista de Tareas" in driver.title

        # Verificar que los elementos principales están presentes
        header = self.safe_find_element(driver, "h1")
        assert header is not None
        assert "Lista de Tareas" in header.text

        # Verificar que el formulario de agregar tarea está presente
        task_input = self.safe_find_element(driver, "[data-testid='task-input']")
        assert task_input is not None
        assert task_input.is_displayed()

        add_button = self.safe_find_element(driver, "[data-testid='add-task-btn']")
        assert add_button is not None
        assert add_button.is_displayed()

        print("[TEST] Página carga correctamente")

    def test_add_new_task(self, driver, flask_app):
        """Prueba agregar una nueva tarea"""
        print("[TEST] Probando agregar nueva tarea")

        driver.get(flask_app.base_url)
        self.wait_for_page_load(driver)

        # Limpiar tareas existentes si las hay
        self._clear_all_tasks(driver)

        # Agregar una nueva tarea
        task_text = f"Tarea E2E {int(time.time())}"  # Texto único

        task_input = self.safe_find_element(driver, "[data-testid='task-input']")
        assert task_input is not None

        task_input.clear()
        task_input.send_keys(task_text)

        add_button = self.safe_find_element(driver, "[data-testid='add-task-btn']")
        assert add_button is not None

        self.safe_click(driver, add_button)

        # Esperar a que aparezca la nueva tarea
        time.sleep(3)
        self.wait_for_page_load(driver)

        # Verificar que la tarea aparece en la lista
        task_items = driver.find_elements(By.CSS_SELECTOR, "[data-testid='task-item']")
        assert len(task_items) >= 1, "No se encontraron tareas después de agregar"

        # Verificar que el texto específico está presente
        page_text = driver.page_source
        assert task_text in page_text, f"No se encontró '{task_text}' en la página"

        print("[TEST] Tarea agregada correctamente")

    def test_complete_task(self, driver, flask_app):
        """Prueba marcar una tarea como completada"""
        print("[TEST] Probando completar tarea")

        driver.get(flask_app.base_url)
        self.wait_for_page_load(driver)

        # Asegurar que hay al menos una tarea
        self._ensure_task_exists(driver, f"Tarea para completar {int(time.time())}")

        # Encontrar el botón de completar tarea
        toggle_button = self.safe_find_element(
            driver, "[data-testid='toggle-task-btn']"
        )
        assert toggle_button is not None

        initial_text = toggle_button.text
        self.safe_click(driver, toggle_button)

        # Esperar a que la página se recargue
        time.sleep(4)
        self.wait_for_page_load(driver)

        # Verificar cambio en el botón
        new_toggle_button = self.safe_find_element(
            driver, "[data-testid='toggle-task-btn']"
        )
        if new_toggle_button:
            assert new_toggle_button.text != initial_text, "El botón no cambió su texto"

        print("[TEST] Tarea completada correctamente")

    def test_delete_task(self, driver, flask_app):
        """Prueba eliminar una tarea"""
        print("[TEST] Probando eliminar tarea")

        driver.get(flask_app.base_url)
        self.wait_for_page_load(driver)

        # Asegurar que hay al menos una tarea
        self._ensure_task_exists(driver, f"Tarea para eliminar {int(time.time())}")

        # Contar tareas iniciales
        initial_tasks = driver.find_elements(
            By.CSS_SELECTOR, "[data-testid='task-item']"
        )
        initial_count = len(initial_tasks)

        # Eliminar la primera tarea
        delete_button = self.safe_find_element(
            driver, "[data-testid='delete-task-btn']"
        )
        assert delete_button is not None

        # Manejar el diálogo de confirmación
        driver.execute_script("window.confirm = function(){return true;}")
        self.safe_click(driver, delete_button)

        # Esperar a que la página se recargue
        time.sleep(4)
        self.wait_for_page_load(driver)

        # Verificar que la tarea fue eliminada
        remaining_tasks = driver.find_elements(
            By.CSS_SELECTOR, "[data-testid='task-item']"
        )
        assert (
            len(remaining_tasks) == initial_count - 1
        ), f"Esperaba {initial_count - 1} tareas, encontré {len(remaining_tasks)}"

        print("[TEST] Tarea eliminada correctamente")

    def test_multiple_tasks_workflow(self, driver, flask_app):
        """Prueba un flujo completo con múltiples tareas"""
        print("[TEST] Probando flujo con múltiples tareas")

        driver.get(flask_app.base_url)
        self.wait_for_page_load(driver)

        # Limpiar todas las tareas
        self._clear_all_tasks(driver)

        # Agregar múltiples tareas
        timestamp = int(time.time())
        tasks = [
            f"Primera tarea {timestamp}",
            f"Segunda tarea {timestamp}",
            f"Tercera tarea {timestamp}",
        ]

        for i, task_text in enumerate(tasks):
            task_input = self.safe_find_element(driver, "[data-testid='task-input']")
            assert task_input is not None

            task_input.clear()
            task_input.send_keys(task_text)

            add_button = self.safe_find_element(driver, "[data-testid='add-task-btn']")
            assert add_button is not None

            self.safe_click(driver, add_button)
            time.sleep(3)  # Pausa entre tareas
            self.wait_for_page_load(driver)

            print(f"  [TEST] Tarea {i + 1} agregada: {task_text}")

        # Verificar que todas las tareas fueron agregadas
        task_items = driver.find_elements(By.CSS_SELECTOR, "[data-testid='task-item']")
        assert len(task_items) >= len(
            tasks
        ), f"Esperaba al menos {len(tasks)} tareas, encontré {len(task_items)}"

        # Completar la primera tarea si existe
        toggle_buttons = driver.find_elements(
            By.CSS_SELECTOR, "[data-testid='toggle-task-btn']"
        )
        if toggle_buttons:
            self.safe_click(driver, toggle_buttons[0])
            time.sleep(3)
            self.wait_for_page_load(driver)

        print("[TEST] Flujo múltiple completado correctamente")

    def test_task_input_validation(self, driver, flask_app):
        """Prueba la validación del input de tareas"""
        print("[TEST] Probando validación de entrada")

        driver.get(flask_app.base_url)
        self.wait_for_page_load(driver)

        # Verificar que el input tiene el atributo required
        task_input = self.safe_find_element(driver, "[data-testid='task-input']")
        assert task_input is not None
        assert task_input.get_attribute("required") is not None

        print("[TEST] Validación de entrada correcta")

    def _ensure_task_exists(self, driver, task_text):
        """Método auxiliar para asegurar que existe al menos una tarea"""
        task_items = driver.find_elements(By.CSS_SELECTOR, "[data-testid='task-item']")

        if len(task_items) == 0:
            print(f"  [TEST] Agregando tarea de prueba: {task_text}")

            task_input = self.safe_find_element(driver, "[data-testid='task-input']")
            if task_input:
                task_input.clear()
                task_input.send_keys(task_text)

                add_button = self.safe_find_element(
                    driver, "[data-testid='add-task-btn']"
                )
                if add_button:
                    self.safe_click(driver, add_button)
                    time.sleep(3)
                    self.wait_for_page_load(driver)

    def _clear_all_tasks(self, driver):
        """Método auxiliar para limpiar todas las tareas"""
        print("  [TEST] Limpiando tareas existentes...")

        max_attempts = 10
        attempts = 0

        while attempts < max_attempts:
            delete_buttons = driver.find_elements(
                By.CSS_SELECTOR, "[data-testid='delete-task-btn']"
            )

            if not delete_buttons:
                print(f"  [TEST] Todas las tareas eliminadas (intentos: {attempts})")
                break

            # Manejar el diálogo de confirmación
            driver.execute_script("window.confirm = function(){return true;}")
            self.safe_click(driver, delete_buttons[0])
            time.sleep(2)
            self.wait_for_page_load(driver)
            attempts += 1

            if attempts >= max_attempts:
                print(f"  [TEST] Se alcanzó el máximo de intentos para limpiar tareas")


if __name__ == "__main__":
    # Configuración para ejecutar las pruebas directamente
    print("[E2E] Ejecutando pruebas E2E directamente")
    print("Para mejores resultados, usa: python -m pytest tests/test_e2e.py -v")

    # Ejecutar con pytest
    import pytest

    pytest.main([__file__, "-v", "--tb=short"])
    import pytest
import time
import os
import threading
import subprocess
import sys
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


class FlaskAppRunner:
    """Clase para manejar la ejecución de la aplicación Flask en las pruebas"""

    def __init__(self, port=5555):
        self.port = port
        self.process = None
        self.base_url = f"http://localhost:{port}"

    def start(self):
        """Inicia la aplicación Flask en un proceso separado"""
        print(f"[E2E] Iniciando Flask en puerto {self.port}...")

        # Configurar entorno
        env = os.environ.copy()
        env["FLASK_ENV"] = "testing"
        env["PORT"] = str(self.port)
        env["HOST"] = "127.0.0.1"
        # Configurar encoding para Windows
        env["PYTHONIOENCODING"] = "utf-8"

        # Cambiar al directorio del proyecto
        project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        try:
            # Iniciar Flask
            self.process = subprocess.Popen(
                [sys.executable, "app.py"],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=project_dir,
                text=True,
            )

            # Esperar a que la aplicación esté lista
            max_attempts = 30
            for attempt in range(max_attempts):
                if self.process.poll() is not None:
                    # El proceso terminó, leer la salida de error
                    stdout, stderr = self.process.communicate()
                    raise Exception(
                        f"Flask app failed to start.\nSTDOUT: {stdout}\nSTDERR: {stderr}"
                    )

                try:
                    response = requests.get(f"{self.base_url}/health", timeout=2)
                    if response.status_code == 200:
                        print(f"[E2E] Flask iniciado correctamente en {self.base_url}")
                        return
                except requests.exceptions.RequestException:
                    pass

                print(f"[E2E] Esperando Flask... intento {attempt + 1}/{max_attempts}")
                time.sleep(2)

            raise Exception("Flask app no respondió después de 60 segundos")

        except Exception as e:
            if self.process:
                self.process.terminate()
            raise Exception(f"Error iniciando Flask: {e}")

    def stop(self):
        """Detiene la aplicación Flask"""
        if self.process:
            print("[E2E] Deteniendo Flask...")
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                print("[E2E] Forzando terminación de Flask...")
                self.process.kill()
                self.process.wait()
            self.process = None


@pytest.fixture(scope="session")
def flask_app():
    """Fixture para iniciar y detener la aplicación Flask"""
    app_runner = FlaskAppRunner()

    try:
        app_runner.start()
        yield app_runner
    finally:
        app_runner.stop()


@pytest.fixture(scope="session")
def driver():
    """Fixture para configurar el driver de Selenium"""
    chrome_options = Options()

    # Configuración para CI/CD y desarrollo local
    chrome_options.add_argument("--headless")  # Ejecutar sin interfaz gráfica
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-web-security")
    chrome_options.add_argument("--allow-running-insecure-content")
    chrome_options.add_argument("--disable-features=VizDisplayCompositor")

    # Configuración adicional para Windows
    if os.name == "nt":
        chrome_options.add_argument("--disable-background-timer-throttling")
        chrome_options.add_argument("--disable-backgrounding-occluded-windows")
        chrome_options.add_argument("--disable-renderer-backgrounding")

    try:
        # Usar webdriver-manager para gestionar ChromeDriver automáticamente
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.implicitly_wait(10)

        print("Chrome WebDriver iniciado correctamente")
        yield driver

    except Exception as e:
        print(f"Error iniciando Chrome WebDriver: {e}")
        raise
    finally:
        try:
            driver.quit()
            print("Chrome WebDriver cerrado")
        except:
            pass


class TestTaskListE2E:
    """Suite de pruebas End-to-End para la aplicación de lista de tareas"""

    def test_page_loads_successfully(self, driver, flask_app):
        """Prueba que la página principal carga correctamente"""
        print(f"[TEST] Probando carga de página en {flask_app.base_url}")

        # Verificar que Flask está respondiendo
        response = requests.get(flask_app.base_url)
        assert (
            response.status_code == 200
        ), f"Flask no responde correctamente: {response.status_code}"

        driver.get(flask_app.base_url)

        # Verificar que el título es correcto
        assert "Lista de Tareas" in driver.title

        # Verificar que los elementos principales están presentes
        header = driver.find_element(By.TAG_NAME, "h1")
        assert "Lista de Tareas" in header.text

        # Verificar que el formulario de agregar tarea está presente
        task_input = driver.find_element(By.CSS_SELECTOR, "[data-testid='task-input']")
        assert task_input.is_displayed()

        add_button = driver.find_element(
            By.CSS_SELECTOR, "[data-testid='add-task-btn']"
        )
        assert add_button.is_displayed()

        print("[TEST] Página carga correctamente")

    def test_add_new_task(self, driver, flask_app):
        """Prueba agregar una nueva tarea"""
        print("[TEST] Probando agregar nueva tarea")

        driver.get(flask_app.base_url)

        # Limpiar tareas existentes si las hay
        self._clear_all_tasks(driver)

        # Verificar estado inicial vacío
        try:
            empty_state = driver.find_element(
                By.CSS_SELECTOR, "[data-testid='empty-state']"
            )
            assert empty_state.is_displayed()
        except:
            print("[TEST] No se encontró estado vacío, continuando...")

        # Agregar una nueva tarea
        task_text = "Tarea de prueba E2E"
        task_input = driver.find_element(By.CSS_SELECTOR, "[data-testid='task-input']")
        task_input.clear()
        task_input.send_keys(task_text)

        add_button = driver.find_element(
            By.CSS_SELECTOR, "[data-testid='add-task-btn']"
        )
        add_button.click()

        # Esperar a que la página se recargue y verificar que la tarea fue agregada
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "[data-testid='task-item']")
            )
        )

        # Verificar que la tarea aparece en la lista
        task_items = driver.find_elements(By.CSS_SELECTOR, "[data-testid='task-item']")
        assert len(task_items) >= 1

        task_text_element = driver.find_element(
            By.CSS_SELECTOR, "[data-testid='task-text']"
        )
        assert task_text in task_text_element.text

        print("[TEST] Tarea agregada correctamente")

    def test_complete_task(self, driver, flask_app):
        """Prueba marcar una tarea como completada"""
        print("[TEST] Probando completar tarea")

        driver.get(flask_app.base_url)

        # Asegurar que hay al menos una tarea
        self._ensure_task_exists(driver, "Tarea para completar")

        # Encontrar el botón de completar tarea
        toggle_button = driver.find_element(
            By.CSS_SELECTOR, "[data-testid='toggle-task-btn']"
        )
        initial_text = toggle_button.text
        toggle_button.click()

        # Esperar a que la página se recargue
        time.sleep(3)

        # Verificar que la tarea está marcada como completada
        task_item = driver.find_element(By.CSS_SELECTOR, "[data-testid='task-item']")
        task_classes = task_item.get_attribute("class")

        # El botón debería haber cambiado su texto
        new_toggle_button = driver.find_element(
            By.CSS_SELECTOR, "[data-testid='toggle-task-btn']"
        )
        assert new_toggle_button.text != initial_text

        print("[TEST] Tarea completada correctamente")

    def test_delete_task(self, driver, flask_app):
        """Prueba eliminar una tarea"""
        print("[TEST] Probando eliminar tarea")

        driver.get(flask_app.base_url)

        # Asegurar que hay al menos una tarea
        self._ensure_task_exists(driver, "Tarea para eliminar")

        # Contar tareas iniciales
        initial_tasks = driver.find_elements(
            By.CSS_SELECTOR, "[data-testid='task-item']"
        )
        initial_count = len(initial_tasks)

        # Eliminar la primera tarea
        delete_button = driver.find_element(
            By.CSS_SELECTOR, "[data-testid='delete-task-btn']"
        )

        # Manejar el diálogo de confirmación
        driver.execute_script("window.confirm = function(){return true;}")
        delete_button.click()

        # Esperar a que la página se recargue
        time.sleep(3)

        # Verificar que la tarea fue eliminada
        remaining_tasks = driver.find_elements(
            By.CSS_SELECTOR, "[data-testid='task-item']"
        )
        assert len(remaining_tasks) == initial_count - 1

        print("[TEST] Tarea eliminada correctamente")

    def test_multiple_tasks_workflow(self, driver, flask_app):
        """Prueba un flujo completo con múltiples tareas"""
        print("[TEST] Probando flujo con múltiples tareas")

        driver.get(flask_app.base_url)

        # Limpiar todas las tareas
        self._clear_all_tasks(driver)

        # Agregar múltiples tareas
        tasks = ["Primera tarea", "Segunda tarea", "Tercera tarea"]

        for i, task_text in enumerate(tasks):
            task_input = driver.find_element(
                By.CSS_SELECTOR, "[data-testid='task-input']"
            )
            task_input.clear()
            task_input.send_keys(task_text)

            add_button = driver.find_element(
                By.CSS_SELECTOR, "[data-testid='add-task-btn']"
            )
            add_button.click()
            time.sleep(2)  # Pausa entre tareas

            print(f"  [TEST] Tarea {i + 1} agregada: {task_text}")

        # Verificar que todas las tareas fueron agregadas
        task_items = driver.find_elements(By.CSS_SELECTOR, "[data-testid='task-item']")
        assert len(task_items) >= len(tasks)

        # Completar la primera tarea
        first_toggle_button = driver.find_elements(
            By.CSS_SELECTOR, "[data-testid='toggle-task-btn']"
        )[0]
        first_toggle_button.click()
        time.sleep(2)

        print("[TEST] Flujo múltiple completado correctamente")

    def test_task_input_validation(self, driver, flask_app):
        """Prueba la validación del input de tareas"""
        print("[TEST] Probando validación de entrada")

        driver.get(flask_app.base_url)

        # Verificar que el input tiene el atributo required
        task_input = driver.find_element(By.CSS_SELECTOR, "[data-testid='task-input']")
        assert task_input.get_attribute("required") is not None

        print("[TEST] Validación de entrada correcta")

    def _ensure_task_exists(self, driver, task_text):
        """Método auxiliar para asegurar que existe al menos una tarea"""
        task_items = driver.find_elements(By.CSS_SELECTOR, "[data-testid='task-item']")

        if len(task_items) == 0:
            print(f"  [TEST] Agregando tarea de prueba: {task_text}")
            # Agregar una tarea si no hay ninguna
            task_input = driver.find_element(
                By.CSS_SELECTOR, "[data-testid='task-input']"
            )
            task_input.clear()
            task_input.send_keys(task_text)

            add_button = driver.find_element(
                By.CSS_SELECTOR, "[data-testid='add-task-btn']"
            )
            add_button.click()

            # Esperar a que se agregue la tarea
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "[data-testid='task-item']")
                )
            )

    def _clear_all_tasks(self, driver):
        """Método auxiliar para limpiar todas las tareas"""
        print("  [TEST] Limpiando tareas existentes...")

        max_attempts = 10
        attempts = 0

        while attempts < max_attempts:
            delete_buttons = driver.find_elements(
                By.CSS_SELECTOR, "[data-testid='delete-task-btn']"
            )

            if not delete_buttons:
                print(f"  [TEST] Todas las tareas eliminadas (intentos: {attempts})")
                break

            # Manejar el diálogo de confirmación
            driver.execute_script("window.confirm = function(){return true;}")
            delete_buttons[0].click()
            time.sleep(1)
            attempts += 1

            if attempts >= max_attempts:
                print(f"  [TEST] Se alcanzó el máximo de intentos para limpiar tareas")


if __name__ == "__main__":
    # Configuración para ejecutar las pruebas directamente
    print("[E2E] Ejecutando pruebas E2E directamente")
    print("Para mejores resultados, usa: python -m pytest tests/test_e2e.py -v")

    # Ejecutar con pytest
    import pytest

    pytest.main([__file__, "-v", "--tb=short"])
