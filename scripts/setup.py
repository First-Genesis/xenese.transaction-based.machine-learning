#!/usr/bin/env python3
"""
TML Platform Setup Script

Automated setup for development and production environments.
"""

import os
import sys
import subprocess
import shutil
import argparse
from pathlib import Path
from typing import List, Optional


class Colors:
    """ANSI color codes for terminal output"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class TMLSetup:
    """TML Platform setup manager"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.venv_path = project_root / "venv"
        
    def print_header(self, message: str):
        """Print colored header"""
        print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}")
        print(f"{Colors.HEADER}{Colors.BOLD}{message.center(60)}{Colors.ENDC}")
        print(f"{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}\n")
    
    def print_step(self, message: str):
        """Print step message"""
        print(f"{Colors.OKBLUE}🔧 {message}{Colors.ENDC}")
    
    def print_success(self, message: str):
        """Print success message"""
        print(f"{Colors.OKGREEN}✅ {message}{Colors.ENDC}")
    
    def print_warning(self, message: str):
        """Print warning message"""
        print(f"{Colors.WARNING}⚠️  {message}{Colors.ENDC}")
    
    def print_error(self, message: str):
        """Print error message"""
        print(f"{Colors.FAIL}❌ {message}{Colors.ENDC}")
    
    def run_command(self, command: List[str], cwd: Optional[Path] = None, check: bool = True) -> subprocess.CompletedProcess:
        """Run shell command with error handling"""
        try:
            result = subprocess.run(
                command,
                cwd=cwd or self.project_root,
                check=check,
                capture_output=True,
                text=True
            )
            return result
        except subprocess.CalledProcessError as e:
            self.print_error(f"Command failed: {' '.join(command)}")
            self.print_error(f"Error: {e.stderr}")
            if check:
                sys.exit(1)
            return e
    
    def check_prerequisites(self):
        """Check system prerequisites"""
        self.print_step("Checking prerequisites...")
        
        # Check Python version
        if sys.version_info < (3, 9):
            self.print_error("Python 3.9+ is required")
            sys.exit(1)
        self.print_success(f"Python {sys.version.split()[0]} found")
        
        # Check required tools
        required_tools = ["git", "docker", "docker-compose"]
        for tool in required_tools:
            result = self.run_command(["which", tool], check=False)
            if result.returncode == 0:
                self.print_success(f"{tool} found")
            else:
                self.print_warning(f"{tool} not found (optional for basic setup)")
    
    def create_virtual_environment(self):
        """Create Python virtual environment"""
        self.print_step("Creating virtual environment...")
        
        if self.venv_path.exists():
            self.print_warning("Virtual environment already exists, skipping...")
            return
        
        self.run_command([sys.executable, "-m", "venv", str(self.venv_path)])
        self.print_success("Virtual environment created")
    
    def install_dependencies(self, dev: bool = True):
        """Install Python dependencies"""
        self.print_step("Installing dependencies...")
        
        pip_path = self.venv_path / "bin" / "pip"
        if sys.platform == "win32":
            pip_path = self.venv_path / "Scripts" / "pip.exe"
        
        # Upgrade pip
        self.run_command([str(pip_path), "install", "--upgrade", "pip"])
        
        # Install main dependencies
        self.run_command([str(pip_path), "install", "-r", "requirements.txt"])
        self.print_success("Main dependencies installed")
        
        # Install development dependencies
        if dev:
            dev_requirements = self.project_root / "requirements-dev.txt"
            if dev_requirements.exists():
                self.run_command([str(pip_path), "install", "-r", str(dev_requirements)])
                self.print_success("Development dependencies installed")
    
    def setup_environment_files(self):
        """Setup environment configuration files"""
        self.print_step("Setting up environment files...")
        
        env_example = self.project_root / ".env.example"
        env_file = self.project_root / ".env"
        
        if env_example.exists() and not env_file.exists():
            shutil.copy(env_example, env_file)
            self.print_success("Environment file created from template")
        else:
            self.print_warning("Environment file already exists or template not found")
    
    def create_directories(self):
        """Create necessary directories"""
        self.print_step("Creating project directories...")
        
        directories = [
            "data",
            "logs",
            "models",
            "artifacts",
            "exports",
            "temp"
        ]
        
        for directory in directories:
            dir_path = self.project_root / directory
            dir_path.mkdir(exist_ok=True)
            
            # Create .gitkeep file
            gitkeep = dir_path / ".gitkeep"
            if not gitkeep.exists():
                gitkeep.touch()
        
        self.print_success("Project directories created")
    
    def setup_git_hooks(self):
        """Setup git pre-commit hooks"""
        self.print_step("Setting up git hooks...")
        
        try:
            # Check if we're in a git repository
            self.run_command(["git", "rev-parse", "--git-dir"])
            
            # Install pre-commit hooks
            python_path = self.venv_path / "bin" / "python"
            if sys.platform == "win32":
                python_path = self.venv_path / "Scripts" / "python.exe"
            
            self.run_command([str(python_path), "-m", "pre_commit", "install"])
            self.print_success("Git hooks installed")
            
        except subprocess.CalledProcessError:
            self.print_warning("Not a git repository or pre-commit not available")
    
    def initialize_database(self):
        """Initialize database schema"""
        self.print_step("Initializing database...")
        
        # This would typically run database migrations
        # For now, we'll just create the init script
        init_script = self.project_root / "docker" / "init-db.sql"
        if init_script.exists():
            self.print_success("Database initialization script found")
        else:
            self.print_warning("Database initialization script not found")
    
    def run_tests(self):
        """Run test suite to verify setup"""
        self.print_step("Running tests to verify setup...")
        
        python_path = self.venv_path / "bin" / "python"
        if sys.platform == "win32":
            python_path = self.venv_path / "Scripts" / "python.exe"
        
        try:
            # Run unit tests only for quick verification
            self.run_command([
                str(python_path), "-m", "pytest", 
                "tests/unit/", "-v", "--tb=short"
            ])
            self.print_success("Tests passed - setup verified!")
        except subprocess.CalledProcessError:
            self.print_warning("Some tests failed - check configuration")
    
    def setup_docker_environment(self):
        """Setup Docker environment"""
        self.print_step("Setting up Docker environment...")
        
        # Check if Docker is available
        result = self.run_command(["docker", "--version"], check=False)
        if result.returncode != 0:
            self.print_warning("Docker not available, skipping Docker setup")
            return
        
        # Build Docker images
        self.run_command(["docker-compose", "build", "--no-cache"])
        self.print_success("Docker images built")
    
    def display_next_steps(self):
        """Display next steps for the user"""
        self.print_header("Setup Complete! Next Steps")
        
        print(f"{Colors.OKCYAN}1. Activate virtual environment:{Colors.ENDC}")
        if sys.platform == "win32":
            print(f"   {Colors.BOLD}venv\\Scripts\\activate{Colors.ENDC}")
        else:
            print(f"   {Colors.BOLD}source venv/bin/activate{Colors.ENDC}")
        
        print(f"\n{Colors.OKCYAN}2. Start the platform:{Colors.ENDC}")
        print(f"   {Colors.BOLD}make start{Colors.ENDC}")
        print(f"   or")
        print(f"   {Colors.BOLD}docker-compose up -d{Colors.ENDC}")
        
        print(f"\n{Colors.OKCYAN}3. Access the dashboards:{Colors.ENDC}")
        print(f"   {Colors.BOLD}http://localhost:8081{Colors.ENDC} - Main Hub")
        print(f"   {Colors.BOLD}http://localhost:8000{Colors.ENDC} - API Server")
        print(f"   {Colors.BOLD}http://localhost:3000{Colors.ENDC} - Grafana (admin/admin123)")
        
        print(f"\n{Colors.OKCYAN}4. Run demos:{Colors.ENDC}")
        print(f"   {Colors.BOLD}python drilling_tml_integration.py{Colors.ENDC}")
        print(f"   {Colors.BOLD}python iot_anomaly_detector.py{Colors.ENDC}")
        
        print(f"\n{Colors.OKCYAN}5. Development commands:{Colors.ENDC}")
        print(f"   {Colors.BOLD}make test{Colors.ENDC} - Run tests")
        print(f"   {Colors.BOLD}make lint{Colors.ENDC} - Code linting")
        print(f"   {Colors.BOLD}make format{Colors.ENDC} - Code formatting")
        
        print(f"\n{Colors.OKGREEN}🎉 TML Platform is ready to use!{Colors.ENDC}")


def main():
    """Main setup function"""
    parser = argparse.ArgumentParser(description="TML Platform Setup")
    parser.add_argument("--no-dev", action="store_true", help="Skip development dependencies")
    parser.add_argument("--no-docker", action="store_true", help="Skip Docker setup")
    parser.add_argument("--no-tests", action="store_true", help="Skip test verification")
    parser.add_argument("--quick", action="store_true", help="Quick setup (minimal components)")
    
    args = parser.parse_args()
    
    # Get project root
    project_root = Path(__file__).parent.parent
    setup = TMLSetup(project_root)
    
    setup.print_header("TML Platform Setup")
    
    try:
        # Core setup steps
        setup.check_prerequisites()
        setup.create_virtual_environment()
        setup.install_dependencies(dev=not args.no_dev)
        setup.setup_environment_files()
        setup.create_directories()
        
        if not args.quick:
            setup.setup_git_hooks()
            setup.initialize_database()
            
            if not args.no_docker:
                setup.setup_docker_environment()
            
            if not args.no_tests:
                setup.run_tests()
        
        setup.display_next_steps()
        
    except KeyboardInterrupt:
        setup.print_error("Setup interrupted by user")
        sys.exit(1)
    except Exception as e:
        setup.print_error(f"Setup failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
