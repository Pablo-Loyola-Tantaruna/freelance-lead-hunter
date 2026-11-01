from __future__ import annotations

# Skills to score positively. Go/Golang is intentionally first-class, not secondary.
STACK_GROUPS = {
    "backend": [
        "java", "spring boot", "spring", "spring webflux", "webflux", "quarkus",
        "go", "golang", "node.js", "nodejs", "nestjs", "nest.js",
        "python", "kotlin", "backend", "microservices", "rest api", "api integration",
    ],
    "cloud_devops": [
        "aws", "azure", "kubernetes", "k8s", "terraform", "docker", "helm",
        "argocd", "argo cd", "github actions", "jenkins", "ci/cd", "devops",
    ],
    "data_messaging": [
        "redis", "kafka", "rabbitmq", "postgresql", "postgres", "sql", "dynamodb",
    ],
    "observability": [
        "grafana", "prometheus", "loki", "tempo", "opentelemetry", "open telemetry",
    ],
    "mobile_automation": [
        "android", "kotlin", "bash", "python automation", "scripting",
    ],
}

STACK = sorted({item for values in STACK_GROUPS.values() for item in values})

INTENT_TERMS = [
    "freelance", "freelancer", "contract", "contractor", "part-time", "part time",
    "short-term", "short term", "project-based", "project based", "consultant",
    "consulting", "one-time", "one time", "hourly", "urgent", "asap", "need help",
    "looking for", "looking for someone", "need someone", "seeking", "remote",
]

DIRECT_NEED_TERMS = [
    "need help", "looking for someone", "need someone", "seeking a consultant",
    "one-time project", "one time project", "urgent", "asap",
]

GEO_POSITIVE = [
    "latam", "latin america", "south america", "peru", "americas", "worldwide",
    "remote", "canada", "united states", "usa", "mexico", "colombia", "chile",
]

NEGATIVE_TERMS = [
    "onsite only", "on-site only", "us citizens only", "u.s. citizens only",
    "security clearance required", "no remote", "full-time onsite", "full time onsite",
    "must be located in the us", "must be based in the us",
]

MARKETPLACE_SOURCES = {"Upwork", "Freelancer", "Workana", "Contra"}

GENERIC_PAGE_PATTERNS = [
    "freelance jobs: work remote & earn online",
    "top spring boot jobs available near",
    "top backend rest api jobs available near",
    "top backend jobs available near",
    "find freelance jobs",
    "hire freelancers",
    "freelance jobs online",
    "best freelance",
]

# Every 3-hour run executes one group. Four groups => every category is searched at least every 12h.
QUERY_GROUPS = {
    "backend_go_java": [
        'site:linkedin.com/posts "looking for" "java developer" contract',
        'site:linkedin.com/posts ("go developer" OR "golang developer") (contract OR freelance)',
        'site:linkedin.com/posts ("need help" OR "looking for someone") ("spring boot" OR "java api")',
        'site:upwork.com/freelance-jobs/apply (java OR "spring boot") backend',
        'site:upwork.com/freelance-jobs/apply (go OR golang) backend',
        'site:freelancer.com/projects (golang OR go) backend',
        'site:workana.com/job (java OR golang OR backend)',
    ],
    "cloud_platform": [
        'site:linkedin.com/posts "need help" (AWS OR Azure)',
        'site:linkedin.com/posts "looking for someone" Kubernetes',
        'site:linkedin.com/posts (terraform OR kubernetes) (consultant OR contractor)',
        'site:upwork.com/freelance-jobs/apply aws kubernetes terraform',
        'site:upwork.com/freelance-jobs/apply azure kubernetes terraform',
        'site:freelancer.com/projects (aws OR azure) kubernetes terraform',
        'site:contra.com (cloud OR devops OR kubernetes) (contract OR freelance)',
    ],
    "api_data_observability": [
        'site:linkedin.com/posts (kafka OR redis OR "rest api") (contractor OR consultant)',
        'site:linkedin.com/posts (grafana OR prometheus OR opentelemetry) consultant',
        'site:linkedin.com/posts "need help" (microservices OR api)',
        'site:upwork.com/freelance-jobs/apply microservices kafka redis',
        'site:upwork.com/freelance-jobs/apply grafana prometheus kubernetes',
        'site:freelancer.com/projects (microservices OR "rest api") backend',
        'site:contra.com (backend OR api) (contract OR freelance)',
    ],
    "buyers_agencies_secondary": [
        'site:linkedin.com/posts (CTO OR founder) "looking for" (backend OR devops)',
        'site:linkedin.com/posts ("software agency" OR "agencia de software") ("contractor" OR "freelance" OR "proyecto")',
        'site:linkedin.com/posts "technical recruiter" (contract OR contractor) (java OR aws OR kubernetes)',
        'site:linkedin.com/posts (nestjs OR node.js OR quarkus) (contract OR freelance)',
        'site:linkedin.com/posts (kotlin OR android) (contract OR freelance)',
        'site:upwork.com/freelance-jobs/apply (nestjs OR node.js OR quarkus)',
        'site:upwork.com/freelance-jobs/apply (kotlin OR android) developer',
    ],
}

CORE_QUERIES = [
    'site:linkedin.com/posts "looking for someone" (backend OR cloud OR devops) remote',
    'site:linkedin.com/posts ("necesito" OR "busco") ("desarrollador" OR "automatización") (freelance OR proyecto)',
]
