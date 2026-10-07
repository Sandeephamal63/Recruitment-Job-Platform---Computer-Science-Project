"""Curated skills gazetteer for CV↔job matching (M4).

Single source of truth for the skill vocabulary: canonical display name (the
key) -> aliases that may appear in free text. Matching is case-insensitive and
uses normalized word(s) with boundary detection so "ts" never matches inside
"its". Extend this dict to tune extraction — do not scatter skill logic across
scorers.

Normalization: lowercase + collapse every non-alphanumeric/#/+/. char to a
space. Aliases are normalized identically at module load, so "C++"/"c plus
plus", "Node.js"/"nodejs", "AWS"/"amazon web services" all resolve cleanly.
"""

import re

# Canonical skill -> variant phrases found in real CVs/job ads.
SKILLS: dict[str, list[str]] = {
    # Languages & paradigms
    "Python": ["python"],
    "Java": ["java"],
    "JavaScript": ["javascript", "javascript es6", "js"],
    "TypeScript": ["typescript", "ts"],
    "PHP": ["php"],
    "Ruby": ["ruby"],
    "Go": ["go", "golang"],
    "Rust": ["rust"],
    "C++": ["c++", "cpp"],
    "C#": ["c#", "c sharp", "dotnet"],
    ".NET": [".net", "dotnet", "asp.net", "aspnet"],
    "C": ["c programming"],
    "SQL": ["sql", "structured query language"],
    "NoSQL": ["nosql"],
    "Pandas": ["pandas"],
    "NumPy": ["numpy"],
    "Matplotlib": ["matplotlib"],
    "Scala": ["scala"],
    "Kotlin": ["kotlin"],
    "Swift": ["swift"],
    "R": ["r language", "r programming"],
    "Bash": ["bash", "shell scripting"],
    "PowerShell": ["powershell"],
    "HTML": ["html", "html5"],
    "CSS": ["css", "css3"],
    "GraphQL": ["graphql"],
    "REST": ["rest", "rest api", "restful"],
    "gRPC": ["grpc"],
    "React Native": ["react native"],
    "Flutter": ["flutter"],
    "Dart": ["dart"],

    # Frameworks & libraries
    "Flask": ["flask"],
    "Django": ["django"],
    "FastAPI": ["fastapi"],
    "Express": ["express", "express.js", "node.js", "nodejs"],
    "Node.js": ["node", "node.js", "nodejs"],
    "Next.js": ["next.js", "nextjs"],
    "Gatsby": ["gatsby"],
    "Angular": ["angular", "angularjs"],
    "React": ["react", "react.js", "reactjs"],
    "Vue": ["vue", "vue.js", "vuejs"],
    "Svelte": ["svelte"],
    "jQuery": ["jquery"],
    "Tailwind CSS": ["tailwind"],
    "Bootstrap": ["bootstrap"],
    "Redux": ["redux"],
    "Spring": ["spring", "spring boot", "springboot"],
    "Hibernate": ["hibernate"],
    "Laravel": ["laravel"],
    "Rails": ["rails", "ruby on rails"],
    "ASP.NET": ["asp.net", "aspnet"],
    "PyTorch": ["pytorch"],
    "TensorFlow": ["tensorflow", "tensor flow"],
    "Keras": ["keras"],
    "Scikit-learn": ["scikit-learn", "sklearn"],
    "OpenCV": ["opencv"],
    "Docker": ["docker", "docker compose", "docker-compose"],
    "Kubernetes": ["kubernetes", "k8s"],
    "Jenkins": ["jenkins"],
    "Git": ["git", "github", "gitlab", "bitbucket", "gitlab ci"],
    "GitHub Actions": ["github actions", "gh actions"],
    "Ansible": ["ansible"],
    "Terraform": ["terraform"],
    "Puppet": ["puppet"],
    "Selenium": ["selenium"],
    "Cypress": ["cypress"],
    "Playwright": ["playwright"],
    "Jest": ["jest"],
    "Mocha": ["mocha"],
    "Pytest": ["pytest"],
    "JUnit": ["junit"],
    "Apache Kafka": ["kafka"],
    "RabbitMQ": ["rabbitmq", "rabbit mq"],
    "Redis": ["redis"],
    "Celery": ["celery"],
    "Airflow": ["airflow"],
    "Spark": ["spark", "apache spark", "pyspark"],
    "Hadoop": ["hadoop", "apache hadoop"],

    # Data
    "MongoDB": ["mongodb", "mongo", "mongoose"],
    "PostgreSQL": ["postgresql", "postgres"],
    "MySQL": ["mysql"],
    "SQLite": ["sqlite"],
    "Oracle Database": ["oracle db", "oracle database", "pl/sql", "plsql"],
    "Microsoft SQL Server": ["sql server", "mssql", "ms sql"],
    "Elasticsearch": ["elasticsearch", "elk"],
    "Snowflake": ["snowflake"],
    "BigQuery": ["bigquery"],
    "Redshift": ["redshift"],
    "ETL": ["etl"],
    "Data Warehousing": ["data warehousing", "data warehouse"],
    "Data Engineering": ["data engineering"],
    "Machine Learning": ["machine learning", "ml"],
    "Deep Learning": ["deep learning", "dl"],
    "Natural Language Processing": ["nlp", "natural language processing"],
    "Computer Vision": ["computer vision"],
    "Statistics": ["statistics", "statistical analysis"],
    "A/B Testing": ["a/b testing", "ab testing", "a b testing"],
    "Data Analysis": ["data analysis", "data analytics"],
    "Data Visualization": ["data visualization", "data viz", "tableau"],
    "Power BI": ["power bi"],
    "Looker": ["looker"],

    # Cloud & infra
    "AWS": ["aws", "amazon web services", "amazon s3", "s3", "ec2", "lambda"],
    "Google Cloud": ["google cloud", "gcp", "google cloud platform"],
    "Azure": ["azure", "microsoft azure"],
    "DevOps": ["devops"],
    "CI/CD": ["ci/cd", "ci cd", "continuous integration", "continuous deployment", "continuous delivery"],
    "Linux": ["linux", "unix"],
    "Networking": ["networking", "tcp/ip", "dns", "http"],
    "Security": ["cybersecurity", "security", "penetration testing", "pentesting"],
    "OWASP": ["owasp"],
    "Nginx": ["nginx"],
    "Apache": ["apache http server", "apache server"],

    # Mobile
    "Android": ["android", "android development"],
    "iOS": ["ios", "ios development"],

    # Testing & quality
    "Unit Testing": ["unit testing", "unit tests"],
    "Test Automation": ["test automation", "automation testing"],
    "TDD": ["tdd", "test driven development"],
    "BDD": ["bdd", "behavior driven development"],
    "Code Review": ["code review"],

    # Architecture & methods
    "Microservices": ["microservices", "micro services"],
    "System Design": ["system design"],
    "Distributed Systems": ["distributed systems"],
    "Agile": ["agile"],
    "Scrum": ["scrum"],
    "Kanban": ["kanban"],
    "Object-oriented Programming": ["oop", "object oriented programming", "object oriented"],
    "Functional Programming": ["functional programming"],
    "Design Patterns": ["design patterns"],
    "SOLID": ["solid principles"],
    "RESTful API Design": ["api design", "restful api"],
    "Message Queues": ["message queues", "messaging"],
    "Concurrency": ["concurrency", "multithreading", "multi threading", "parallel programming"],

    # Product & workplace basics
    "Project Management": ["project management", "pm tools", "jira", "trello"],
    "Communication": ["communication", "communication skills"],
    "Leadership": ["leadership", "team leadership"],
    "Mentoring": ["mentoring", "mentorship"],
    "Documentation": ["technical documentation", "documentation"],
}

# Keep the gazetteer warning-light and honest about overlaps.
assert len({str(k).lower() for k in SKILLS}) == len(SKILLS), "duplicate canonical skills"


def _normalize(text: str) -> str:
    """Lowercase and collapse non-word-ish chars so aliases match across
    punctuation/casing variants ("C++", "Node.js", "ci/cd")."""
    return re.sub(r"[^a-z0-9+#.]+", " ", (text or "").lower()).strip()


# Pre-normalized alias index: normalized alias -> canonical skill.
_ALIAS_INDEX: dict[str, str] = {}
for _skill, _aliases in SKILLS.items():
    for _alias in _aliases:
        _ALIAS_INDEX[_normalize(_alias)] = _skill


def extract_skills(text: str) -> set[str]:
    """Return the canonical skill names that appear in ``text``.

    Boundary-aware: a normalized alias must appear as a delimited token so
    "js" isn't found inside "a/jsons" and "ts" inside "its".
    """
    normalized = _normalize(text)
    padded = f" {normalized} "
    found: set[str] = set()
    for alias, skill in _ALIAS_INDEX.items():
        if not alias:
            continue
        if f" {alias} " in padded:
            found.add(skill)
    return found


def diff_skills(required_skills: list[str], text: str) -> tuple[list[str], list[str]]:
    """Split ``required_skills`` into those present in ``text`` and those absent.

    A required skill counts as present if it was found by the gazetteer OR its
    own normalized phrase appears verbatim in the text (so free-form job skills
    that aren't yet in the gazetteer still resolve when the CV names them).
    """
    found = extract_skills(text)
    normalized_found = {_normalize(skill) for skill in found}
    normalized_text = f" {_normalize(text)} "
    matched: list[str] = []
    missing: list[str] = []
    for skill in required_skills:
        normalized = _normalize(skill)
        present = normalized in normalized_found or (
            normalized and f" {normalized} " in normalized_text
        )
        if present:
            matched.append(skill)
        else:
            missing.append(skill)
    return matched, missing