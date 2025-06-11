from locust import HttpUser, task, between
import json
import random


class TaskListUser(HttpUser):
    """
    Clase de usuario para pruebas de carga en la aplicación de lista de tareas
    """

    # Tiempo de espera entre tareas del usuario (1-3 segundos)
    wait_time = between(1, 3)

    def on_start(self):
        """Método que se ejecuta cuando inicia cada usuario simulado"""
        # Verificar que la aplicación esté disponible
        self.client.get("/health")

        # Lista de tareas de ejemplo para las pruebas
        self.sample_tasks = [
            "Revisar correos electrónicos",
            "Preparar presentación para cliente",
            "Llamar al proveedor",
            "Actualizar documentación del proyecto",
            "Reunión de equipo",
            "Revisar código de la aplicación",
            "Planificar sprint siguiente",
            "Hacer backup de datos",
            "Actualizar dependencias del proyecto",
            "Escribir tests unitarios",
            "Optimizar base de datos",
            "Configurar entorno de producción"
        ]

        # Almacenar IDs de tareas creadas por este usuario
        self.created_task_ids = []

    @task(5)
    def view_homepage(self):
        """
        Tarea más común: ver la página principal
        Peso: 5 (se ejecutará 5 veces más frecuentemente que tareas con peso 1)
        """
        with self.client.get("/", catch_response=True) as response:
            if response.status_code == 200:
                # Verificar que la página contiene elementos esperados
                if "Lista de Tareas" in response.text:
                    response.success()
                else:
                    response.failure("Homepage doesn't contain expected content")
            else:
                response.failure(f"Homepage returned status code: {response.status_code}")

    @task(3)
    def add_task_via_form(self):
        """
        Agregar tarea usando el formulario web
        Peso: 3
        """
        task_text = random.choice(self.sample_tasks)

        with self.client.post("/add",
                              data={"task": task_text},
                              catch_response=True) as response:
            if response.status_code == 302:  # Redirect después de agregar
                response.success()
            else:
                response.failure(f"Add task form returned status code: {response.status_code}")

    @task(2)
    def get_tasks_via_api(self):
        """
        Obtener tareas usando la API REST
        Peso: 2
        """
        with self.client.get("/api/tasks", catch_response=True) as response:
            if response.status_code == 200:
                try:
                    tasks = response.json()
                    if isinstance(tasks, list):
                        response.success()
                        # Guardar algunos IDs de tareas para operaciones posteriores
                        if tasks and len(self.created_task_ids) < 5:
                            self.created_task_ids.extend([task['id'] for task in tasks[-2:]])
                    else:
                        response.failure("API didn't return a list")
                except json.JSONDecodeError:
                    response.failure("API response is not valid JSON")
            else:
                response.failure(f"API returned status code: {response.status_code}")

    @task(2)
    def add_task_via_api(self):
        """
        Agregar tarea usando la API REST
        Peso: 2
        """
        task_text = random.choice(self.sample_tasks)
        task_data = {"text": task_text}

        with self.client.post("/api/tasks",
                              json=task_data,
                              headers={"Content-Type": "application/json"},
                              catch_response=True) as response:
            if response.status_code == 201:
                try:
                    created_task = response.json()
                    if 'id' in created_task:
                        self.created_task_ids.append(created_task['id'])
                        response.success()
                    else:
                        response.failure("API response doesn't contain task ID")
                except json.JSONDecodeError:
                    response.failure("API response is not valid JSON")
            else:
                response.failure(f"API add task returned status code: {response.status_code}")

    @task(1)
    def toggle_task_status(self):
        """
        Cambiar estado de una tarea (completar/descompletar)
        Peso: 1
        """
        if not self.created_task_ids:
            # Si no tenemos IDs de tareas, primero obtenemos algunas
            self.get_tasks_via_api()

        if self.created_task_ids:
            task_id = random.choice(self.created_task_ids)

            with self.client.get(f"/toggle/{task_id}", catch_response=True) as response:
                if response.status_code == 302:  # Redirect después de toggle
                    response.success()
                else:
                    response.failure(f"Toggle task returned status code: {response.status_code}")

    @task(1)
    def delete_task(self):
        """
        Eliminar una tarea
        Peso: 1 (menos frecuente)
        """
        if not self.created_task_ids:
            # Si no tenemos IDs de tareas, primero obtenemos algunas
            self.get_tasks_via_api()

        if self.created_task_ids:
            task_id = self.created_task_ids.pop()  # Remover el ID de nuestra lista local

            with self.client.get(f"/delete/{task_id}", catch_response=True) as response:
                if response.status_code == 302:  # Redirect después de eliminar
                    response.success()
                else:
                    response.failure(f"Delete task returned status code: {response.status_code}")

    @task(1)
    def health_check(self):
        """
        Verificar el endpoint de health check
        Peso: 1
        """
        with self.client.get("/health", catch_response=True) as response:
            if response.status_code == 200:
                try:
                    health_data = response.json()
                    if health_data.get('status') == 'healthy':
                        response.success()
                    else:
                        response.failure("Health check status is not healthy")
                except json.JSONDecodeError:
                    response.failure("Health check response is not valid JSON")
            else:
                response.failure(f"Health check returned status code: {response.status_code}")


class HeavyUser(HttpUser):
    """
    Usuario que simula carga pesada para pruebas de estrés
    """

    wait_time = between(0.1, 0.5)  # Menos tiempo de espera

    def on_start(self):
        """Inicialización del usuario pesado"""
        self.sample_tasks = [
            f"Tarea pesada {i}" for i in range(1, 21)
        ]

    @task(10)
    def rapid_homepage_access(self):
        """Acceso rápido y frecuente a la página principal"""
        self.client.get("/")

    @task(5)
    def rapid_api_calls(self):
        """Llamadas rápidas a la API"""
        self.client.get("/api/tasks")

    @task(3)
    def rapid_task_creation(self):
        """Creación rápida de tareas"""
        task_data = {"text": f"Tarea rápida {random.randint(1, 1000)}"}
        self.client.post("/api/tasks", json=task_data)


class MobileUser(HttpUser):
    """
    Usuario que simula el comportamiento desde dispositivos móviles
    """

    wait_time = between(2, 5)  # Más tiempo de espera (conexión móvil más lenta)

    def on_start(self):
        """Configurar headers para simular dispositivo móvil"""
        self.client.headers.update({
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1'
        })

        self.mobile_tasks = [
            "Revisar notificaciones",
            "Responder mensaje",
            "Tomar foto de documento",
            "Ubicación de reunión",
            "Recordatorio medicamento"
        ]

    @task(8)
    def mobile_homepage_view(self):
        """Vista de homepage desde móvil"""
        self.client.get("/")

    @task(2)
    def mobile_add_task(self):
        """Agregar tarea desde móvil"""
        task_text = random.choice(self.mobile_tasks)
        self.client.post("/add", data={"task": task_text})


class StressTestUser(HttpUser):
    """
    Usuario para pruebas de estrés con patrones más agresivos
    """

    wait_time = between(0.1, 1)

    def on_start(self):
        """Inicialización para pruebas de estrés"""
        self.stress_counter = 0

    @task
    def stress_test_workflow(self):
        """
        Flujo de trabajo que combina múltiples operaciones
        """
        self.stress_counter += 1

        # Crear múltiples tareas rápidamente
        for i in range(3):
            task_data = {"text": f"Stress task {self.stress_counter}-{i}"}
            self.client.post("/api/tasks", json=task_data)

        # Verificar el estado
        self.client.get("/api/tasks")
        self.client.get("/")

        # Health check
        self.client.get("/health")


class APIOnlyUser(HttpUser):
    """
    Usuario que solo utiliza endpoints de API (sin interfaz web)
    """

    wait_time = between(0.5, 2)

    def on_start(self):
        """Configuración para usuario API-only"""
        self.task_ids = []
        self.api_tasks = [
            "API Task - Data Processing",
            "API Task - Batch Update",
            "API Task - Sync Operation",
            "API Task - Cleanup Job",
            "API Task - Report Generation"
        ]

    @task(5)
    def api_create_task(self):
        """Crear tarea via API"""
        task_data = {"text": random.choice(self.api_tasks)}

        with self.client.post("/api/tasks", json=task_data, catch_response=True) as response:
            if response.status_code == 201:
                try:
                    task = response.json()
                    self.task_ids.append(task['id'])
                    response.success()
                except (json.JSONDecodeError, KeyError):
                    response.failure("Invalid API response")
            else:
                response.failure(f"API create failed: {response.status_code}")

    @task(8)
    def api_list_tasks(self):
        """Listar tareas via API"""
        with self.client.get("/api/tasks", catch_response=True) as response:
            if response.status_code == 200:
                try:
                    tasks = response.json()
                    if isinstance(tasks, list):
                        # Actualizar nuestra lista de IDs
                        if tasks:
                            self.task_ids = [task['id'] for task in tasks[-5:]]
                        response.success()
                    else:
                        response.failure("API response is not a list")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            else:
                response.failure(f"API list failed: {response.status_code}")

    @task(1)
    def api_health_check(self):
        """Health check via API"""
        self.client.get("/health")


if __name__ == "__main__":
    # Este archivo puede ejecutarse directamente para pruebas rápidas
    import os
    import sys

    # Agregar el directorio padre al path para importar la app
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    # Configuración básica para ejecutar locust
    print("=" * 60)
    print("🚀 LOCUST - PRUEBAS DE PERFORMANCE")
    print("=" * 60)
    print("\nPara ejecutar las pruebas de performance:")
    print("locust -f tests/locustfile.py --host=http://localhost:5000")
    print("\n📊 Tipos de usuarios disponibles:")
    print("- TaskListUser: Usuario normal con comportamiento típico")
    print("- HeavyUser: Usuario con carga pesada")
    print("- MobileUser: Usuario simulando dispositivo móvil")
    print("- StressTestUser: Usuario para pruebas de estrés")
    print("- APIOnlyUser: Usuario que solo usa endpoints API")
    print("\n💡 Ejemplos de uso:")
    print("# Usuario normal (10 usuarios, 2 por segundo)")
    print("locust -f tests/locustfile.py TaskListUser --host=http://localhost:5000 --users 10 --spawn-rate 2")
    print("\n# Prueba de estrés (50 usuarios, 5 por segundo, 5 minutos)")
    print(
        "locust -f tests/locustfile.py StressTestUser --host=http://localhost:5000 --users 50 --spawn-rate 5 --run-time 300s --headless")
    print("\n# Múltiples tipos de usuarios")
    print("locust -f tests/locustfile.py TaskListUser,MobileUser --host=http://localhost:5000")
    print("\n🌐 Interfaz web: http://localhost:8089")
    print("=" * 60)