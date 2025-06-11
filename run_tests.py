#!/usr/bin/env python3
"""
Script para ejecutar todas las pruebas del proyecto Lista de Tareas
Incluye pruebas E2E y de performance con diferentes opciones
"""

import subprocess
import sys
import time
import os
import argparse
import threading
from pathlib import Path


class TestRunner:
    """Clase para gestionar la ejecución de pruebas"""

    def __init__(self):
        self.flask_process = None
        self.base_dir = Path(__file__).parent

    def run_command(self, command, description="", timeout=None):
        """Ejecuta un comando y retorna el resultado"""
        print(f"\n{'=' * 60}")
        print(f"🔧 {description}")
        print(f"Comando: {command}")
        print(f"{'=' * 60}")

        try:
            result = subprocess.run(
                command,
                shell=True,
                check=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.base_dir,
            )

            if result.stdout:
                print(result.stdout)
            return True, result.stdout

        except subprocess.CalledProcessError as e:
            print(f"❌ Error ejecutando comando (código {e.returncode}):")
            if e.stderr:
                print(f"Error: {e.stderr}")
            if e.stdout:
                print(f"Output: {e.stdout}")
            return False, e.stderr

        except subprocess.TimeoutExpired:
            print(f"❌ Comando excedió el timeout de {timeout} segundos")
            return False, "Timeout"

    def start_flask_app(self, port=5000):
        """Inicia la aplicación Flask en background"""
        print(f"🚀 Iniciando aplicación Flask en puerto {port}...")

        env = os.environ.copy()
        env["FLASK_ENV"] = "testing"
        env["PORT"] = str(port)

        try:
            self.flask_process = subprocess.Popen(
                [sys.executable, "app.py"],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.base_dir,
            )

            # Esperar a que la app esté lista
            max_attempts = 15
            for i in range(max_attempts):
                try:
                    import requests

                    response = requests.get(
                        f"http://localhost:{port}/health", timeout=2
                    )
                    if response.status_code == 200:
                        print(f"✅ Aplicación Flask iniciada en puerto {port}")
                        return True
                except:
                    pass

                if self.flask_process.poll() is not None:
                    print("❌ El proceso Flask terminó inesperadamente")
                    return False

                print(f"⏳ Esperando Flask... ({i + 1}/{max_attempts})")
                time.sleep(2)

            print("❌ Flask no respondió después de 30 segundos")
            return False

        except Exception as e:
            print(f"❌ Error iniciando Flask: {e}")
            return False

    def stop_flask_app(self):
        """Detiene la aplicación Flask"""
        if self.flask_process:
            print("🛑 Deteniendo aplicación Flask...")
            self.flask_process.terminate()
            try:
                self.flask_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.flask_process.kill()

            self.flask_process = None

    def run_e2e_tests(self, verbose=True):
        """Ejecuta las pruebas E2E"""
        print("\n" + "=" * 60)
        print("🧪 EJECUTANDO PRUEBAS E2E")
        print("=" * 60)

        # Verificar que existen los archivos de prueba
        e2e_test_file = self.base_dir / "tests" / "test_e2e.py"
        if not e2e_test_file.exists():
            print(f"❌ No se encontró el archivo de pruebas E2E: {e2e_test_file}")
            return False

        # Construir comando pytest
        cmd_parts = ["python", "-m", "pytest", "tests/test_e2e.py"]

        if verbose:
            cmd_parts.extend(["-v", "--tb=short"])

        cmd_parts.extend(
            ["--color=yes", "--durations=10", "-x"]  # Parar en el primer fallo
        )

        command = " ".join(cmd_parts)
        success, output = self.run_command(
            command, "Ejecutando pruebas End-to-End", timeout=300
        )

        return success

    def run_performance_tests(
        self, users=10, duration=60, host="http://localhost:5000"
    ):
        """Ejecuta las pruebas de performance con Locust"""
        print("\n" + "=" * 60)
        print("📊 EJECUTANDO PRUEBAS DE PERFORMANCE")
        print("=" * 60)

        # Verificar que existe el archivo de Locust
        locust_file = self.base_dir / "tests" / "locustfile.py"
        if not locust_file.exists():
            print(f"❌ No se encontró el archivo de Locust: {locust_file}")
            return False

        # Configurar archivos de salida
        timestamp = int(time.time())
        html_report = f"performance-report-{timestamp}.html"
        csv_prefix = f"performance-results-{timestamp}"

        # Construir comando Locust
        command = f"""locust -f tests/locustfile.py \
            --host={host} \
            --users={users} \
            --spawn-rate=2 \
            --run-time={duration}s \
            --html={html_report} \
            --csv={csv_prefix} \
            --headless"""

        success, output = self.run_command(
            command,
            f"Ejecutando pruebas de performance ({users} usuarios, {duration}s)",
            timeout=duration + 60,
        )

        if success:
            print(f"\n📋 Reportes generados:")
            print(f"  - HTML: {html_report}")
            print(f"  - CSV Stats: {csv_prefix}_stats.csv")
            print(f"  - CSV Failures: {csv_prefix}_failures.csv")

        return success

    def run_lint_checks(self):
        """Ejecuta verificaciones de linting"""
        print("\n" + "=" * 60)
        print("🔍 VERIFICACIONES DE CÓDIGO")
        print("=" * 60)

        checks = [
            (
                "flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics",
                "Verificando errores críticos de sintaxis",
            ),
            (
                "flake8 . --count --exit-zero --max-complexity=10 --max-line-length=88 --statistics",
                "Verificando estilo de código",
            ),
        ]

        all_passed = True

        for command, description in checks:
            success, _ = self.run_command(command, description, timeout=30)
            if not success:
                all_passed = False

        return all_passed

    def run_full_test_suite(self, args):
        """Ejecuta la suite completa de pruebas"""
        print("🎯 INICIANDO SUITE COMPLETA DE PRUEBAS")
        print("=" * 60)

        results = {"lint": False, "e2e": False, "performance": False}

        try:
            # 1. Verificaciones de linting
            if not args.skip_lint:
                print("\n📋 Paso 1: Verificaciones de código")
                results["lint"] = self.run_lint_checks()
            else:
                print("\n⏭️  Saltando verificaciones de linting")
                results["lint"] = True

            # 2. Iniciar Flask para las pruebas
            if not args.skip_e2e or not args.skip_performance:
                if not self.start_flask_app(port=args.port):
                    print(
                        "❌ No se pudo iniciar Flask. Saltando pruebas que requieren servidor."
                    )
                    return results

            # 3. Pruebas E2E
            if not args.skip_e2e:
                print("\n📋 Paso 2: Pruebas End-to-End")
                results["e2e"] = self.run_e2e_tests(verbose=args.verbose)
            else:
                print("\n⏭️  Saltando pruebas E2E")
                results["e2e"] = True

            # 4. Pruebas de Performance
            if not args.skip_performance:
                print("\n📋 Paso 3: Pruebas de Performance")
                results["performance"] = self.run_performance_tests(
                    users=args.users,
                    duration=args.duration,
                    host=f"http://localhost:{args.port}",
                )
            else:
                print("\n⏭️  Saltando pruebas de performance")
                results["performance"] = True

        finally:
            # Limpiar recursos
            self.stop_flask_app()

        return results

    def print_final_report(self, results, start_time):
        """Imprime el reporte final de las pruebas"""
        end_time = time.time()
        duration = end_time - start_time

        print("\n" + "=" * 60)
        print("📊 REPORTE FINAL DE PRUEBAS")
        print("=" * 60)

        print(f"⏱️  Duración total: {duration:.1f} segundos")
        print(f"📅 Fecha: {time.strftime('%Y-%m-%d %H:%M:%S')}")

        print("\n📋 Resultados por categoría:")
        status_icons = {True: "✅", False: "❌", None: "⏭️"}

        for test_type, result in results.items():
            icon = status_icons.get(result, "❓")
            status = "PASÓ" if result else "FALLÓ" if result is False else "SALTADO"
            print(f"  {icon} {test_type.upper()}: {status}")

        # Calcular estadísticas
        executed_tests = [r for r in results.values() if r is not None]
        passed_tests = [r for r in executed_tests if r is True]

        if executed_tests:
            success_rate = (len(passed_tests) / len(executed_tests)) * 100
            print(
                f"\n📈 Tasa de éxito: {success_rate:.1f}% ({len(passed_tests)}/{len(executed_tests)})"
            )

        # Determinar resultado general
        overall_success = all(result is not False for result in results.values())

        if overall_success:
            print("\n🎉 ¡TODAS LAS PRUEBAS COMPLETADAS EXITOSAMENTE!")
        else:
            print("\n⚠️  ALGUNAS PRUEBAS FALLARON")
            print("Revisa los logs anteriores para más detalles")

        print("=" * 60)

        return overall_success


def main():
    """Función principal"""
    parser = argparse.ArgumentParser(
        description="Ejecuta las pruebas del proyecto Lista de Tareas",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  python run_tests.py                              # Suite completa
  python run_tests.py --skip-performance          # Solo E2E y linting
  python run_tests.py --e2e-only                  # Solo pruebas E2E
  python run_tests.py --performance-only --users 20 --duration 120
  python run_tests.py --quick                     # Pruebas rápidas
        """,
    )

    # Argumentos de control de pruebas
    parser.add_argument(
        "--skip-lint", action="store_true", help="Saltar verificaciones de linting"
    )
    parser.add_argument("--skip-e2e", action="store_true", help="Saltar pruebas E2E")
    parser.add_argument(
        "--skip-performance", action="store_true", help="Saltar pruebas de performance"
    )

    # Atajos
    parser.add_argument(
        "--e2e-only", action="store_true", help="Ejecutar solo pruebas E2E"
    )
    parser.add_argument(
        "--performance-only",
        action="store_true",
        help="Ejecutar solo pruebas de performance",
    )
    parser.add_argument(
        "--lint-only",
        action="store_true",
        help="Ejecutar solo verificaciones de linting",
    )
    parser.add_argument(
        "--quick", action="store_true", help="Pruebas rápidas (lint + E2E básico)"
    )

    # Configuración de pruebas de performance
    parser.add_argument(
        "--users",
        type=int,
        default=10,
        help="Número de usuarios para pruebas de performance (default: 10)",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Duración de pruebas de performance en segundos (default: 60)",
    )

    # Configuración general
    parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="Puerto para la aplicación Flask (default: 5000)",
    )
    parser.add_argument("--verbose", action="store_true", help="Output detallado")

    args = parser.parse_args()

    # Procesar atajos
    if args.e2e_only:
        args.skip_lint = True
        args.skip_performance = True
    elif args.performance_only:
        args.skip_lint = True
        args.skip_e2e = True
    elif args.lint_only:
        args.skip_e2e = True
        args.skip_performance = True
    elif args.quick:
        args.skip_performance = True
        args.duration = 30

    # Inicializar runner
    runner = TestRunner()
    start_time = time.time()

    try:
        results = runner.run_full_test_suite(args)
        success = runner.print_final_report(results, start_time)

        # Código de salida apropiado
        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        print("\n\n⚠️  Pruebas interrumpidas por el usuario")
        runner.stop_flask_app()
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ Error inesperado: {e}")
        runner.stop_flask_app()
        sys.exit(1)


if __name__ == "__main__":
    main()
