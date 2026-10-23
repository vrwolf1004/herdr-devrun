"""서비스 추가 흐름에서 고르는 기술별 기본값. 분류를 고르고, 기술을 고르면 명령과 포트가 채워진다.

- windows / unix: 실행 명령. OS 별 명령이 다르면 설정에 command_windows / command_unix 로 나뉘어 저장된다.
- port: 기본 포트. None 이면 포트를 고정하지 않는 도구라 비워 둔다.
- source: "docs" 는 공식 문서·기본 설정에서 확인한 값, "estimate" 는 추정 값이다 (docs/usage.md 의 프리셋 표 참고).
"""

CATEGORIES = ("frontend", "backend", "middleware", "database", "other")

PRESETS = {
    "frontend": (
        {"id": "react", "label": "React (Vite)", "windows": "npm run dev", "unix": "npm run dev",
         "port": None, "source": "docs"},
        {"id": "nextjs", "label": "Next.js", "windows": "npm run dev", "unix": "npm run dev",
         "port": 3000, "source": "docs"},
        {"id": "vue", "label": "Vue", "windows": "npm run dev", "unix": "npm run dev",
         "port": 5173, "source": "estimate"},
        {"id": "angular", "label": "Angular", "windows": "npx ng serve", "unix": "npx ng serve",
         "port": 4200, "source": "docs"},
        {"id": "vite", "label": "Vite", "windows": "npm run dev", "unix": "npm run dev",
         "port": 5173, "source": "docs"},
    ),
    "backend": (
        {"id": "spring-gradle", "label": "Spring Boot (Gradle)", "windows": "gradlew.bat bootRun",
         "unix": "./gradlew bootRun", "port": 8080, "source": "docs"},
        {"id": "spring-maven", "label": "Spring Boot (Maven)", "windows": "mvnw.cmd spring-boot:run",
         "unix": "./mvnw spring-boot:run", "port": 8080, "source": "docs"},
        {"id": "aspnet", "label": "ASP.NET Core", "windows": "dotnet run", "unix": "dotnet run",
         "port": 5000, "source": "estimate"},
        {"id": "php-builtin", "label": "PHP (built-in server)", "windows": "php -S localhost:8000",
         "unix": "php -S localhost:8000", "port": 8000, "source": "estimate"},
        {"id": "laravel", "label": "PHP (Laravel)", "windows": "php artisan serve",
         "unix": "php artisan serve", "port": 8000, "source": "estimate"},
        {"id": "express", "label": "Node.js (Express)", "windows": "npm start", "unix": "npm start",
         "port": 3000, "source": "estimate"},
        {"id": "django", "label": "Django", "windows": "python manage.py runserver",
         "unix": "python3 manage.py runserver", "port": 8000, "source": "docs"},
        {"id": "fastapi", "label": "FastAPI", "windows": "uvicorn main:app --reload",
         "unix": "uvicorn main:app --reload", "port": 8000, "source": "estimate"},
    ),
    "middleware": (
        {"id": "redis", "label": "Redis", "windows": "redis-server", "unix": "redis-server",
         "port": 6379, "source": "estimate"},
    ),
    "database": (
        {"id": "postgresql", "label": "PostgreSQL", "windows": "postgres -D data", "unix": "postgres -D data",
         "port": 5432, "source": "estimate"},
        {"id": "mysql", "label": "MySQL", "windows": "mysqld --console", "unix": "mysqld",
         "port": 3306, "source": "estimate"},
    ),
    "other": (),  # 기타는 직접 입력만 한다
}


def find(category, tech):
    return next((each for each in PRESETS.get(category, ()) if each["id"] == tech), None)
