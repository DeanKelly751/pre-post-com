"""Static sample scenarios for the compaction benchmarking tool.

Provides a diverse set of test scenarios that stress different compaction
strategies. Each scenario type exercises a different aspect of compaction:

- Short prose:  baseline difficulty — small context, clean text
- Long prose:   tests input pruning at scale — many sentences to filter
- JSON-heavy:   tests structural compression (JSON arrays, API responses)
- Code-heavy:   tests code-aware compression (AST, comments, whitespace)
- Mixed:        real-world RAG retrieval — prose + code + JSON + tables

No network access required. All data is static.
"""

import json
from pathlib import Path

SCENARIOS_FILE = Path(__file__).parent / "scenarios.json"

SCENARIOS = [
    # ── Scenario 1: Short prose (~1,600 tokens) ──────────────────────
    {
        "id": "short-prose",
        "title": "SWE-bench: Can Language Models Resolve Real-World GitHub Issues?",
        "category": "short-prose",
        "category_label": "Short Prose (~1,600 tok)",
        "description": "A focused paper excerpt. Tests baseline compaction on clean, relevant prose.",
        "authors": ["Carlos E. Jimenez", "John Yang", "Alexander Wettig"],
        "query": "What is the main research contribution of this paper?",
        "text": """SWE-bench: Can Language Models Resolve Real-World GitHub Issues?

Abstract: Language models have demonstrated impressive abilities in code generation, but can they fix real-world software bugs? We introduce SWE-bench, a benchmark that evaluates language models on 2,294 real-world software engineering tasks sourced from GitHub issues and corresponding pull requests across 12 popular Python repositories. Given a codebase and an issue description, a language model is tasked with generating a patch that resolves the issue.

1. Introduction
Software engineering involves much more than writing code from scratch. Professional developers spend a significant portion of their time understanding existing codebases, debugging issues, and implementing fixes that integrate seamlessly with established patterns and conventions. While recent advances in large language models have shown remarkable code generation capabilities on benchmarks like HumanEval and MBPP, these benchmarks primarily test the ability to write short, self-contained functions. They do not capture the complexity of real-world software engineering, which requires understanding large codebases, navigating multiple files, and producing patches that pass existing test suites.

To bridge this gap, we introduce SWE-bench, a benchmark consisting of 2,294 task instances drawn from real GitHub issues and pull requests. Each task instance provides: (1) a repository at a specific commit, (2) a natural language description of the issue to be resolved, and (3) a set of tests that verify the correctness of the solution. The model must generate a code patch that, when applied to the repository, causes the failing tests to pass while not breaking any previously passing tests.

2. Related Work
Code generation benchmarks have evolved significantly. HumanEval introduced 164 hand-written Python programming problems with test cases. MBPP provided 974 crowd-sourced Python programming problems. CodeContests collected competitive programming problems from platforms like Codeforces. However, all these benchmarks focus on generating standalone functions or programs, not modifying existing codebases. On the software engineering side, Defects4J collected real bugs from Java projects, and BugsInPy did the same for Python projects. However, these datasets were designed for software testing research rather than evaluating language model capabilities.

SWE-bench differs from prior work in several important ways. First, the tasks come from real GitHub issues, capturing the full complexity and variety of real-world software bugs. Second, the evaluation is fully automated using existing test suites, ensuring reproducibility. Third, the benchmark spans 12 popular repositories including Django, Flask, scikit-learn, and sympy, providing diverse testing contexts.

3. Dataset Construction
We construct SWE-bench through a systematic pipeline. We identify merged pull requests that (a) resolve a GitHub issue, (b) include at least one test that fails before the PR and passes after, and (c) come from repositories with well-maintained test suites. For each qualifying PR, we create a task instance by recording the repository state before the PR, the issue description, and the relevant test cases.

The repositories included in SWE-bench are: astropy, django, flask, matplotlib, pylint, pytest, requests, scikit-learn, seaborn, sphinx, sympy, and xarray. These were selected because they are widely used, well-maintained, and have comprehensive test suites. The resulting dataset contains 2,294 task instances, with issues ranging from simple one-line fixes to complex multi-file changes.

4. Evaluation Framework
We evaluate models using a retrieval-augmented generation setup. Given the issue description, we first retrieve relevant code files using BM25. The retrieved files, along with the issue description, are provided as context to the language model, which must generate a unified diff patch. The patch is then applied to the repository and validated against the test suite.

We evaluate several state-of-the-art models: Claude 2, GPT-4, and GPT-3.5-turbo, as well as the open-source models SWE-Llama 7B and 13B, which we fine-tune specifically for this task. We also experiment with different retrieval strategies and context window configurations.

5. Results
Our evaluation reveals several key findings. First, the task is extremely challenging for current language models. The best-performing model, Claude 2, resolves only 4.8% of issues when provided with the relevant files. When combined with BM25 retrieval, GPT-4 achieves 1.7% resolution rate. These low numbers highlight the significant gap between current model capabilities and real-world software engineering requirements.

Second, we find that models struggle most with tasks requiring changes across multiple files, understanding complex control flow, and reasoning about the interaction between different components. Tasks involving simple string manipulation or configuration changes are more frequently solved.

Third, fine-tuning on similar tasks provides modest improvements. SWE-Llama 13B achieves 3.2% resolution rate, demonstrating that specialised training can help but does not close the gap dramatically.

6. Analysis
Error analysis reveals common failure modes: (a) models generate syntactically valid but semantically incorrect patches, (b) models modify the wrong files or functions, (c) models fail to account for the broader context of the change, and (d) models generate patches that fix the immediate symptom but not the root cause. These findings suggest that significant advances in code understanding and reasoning are needed before language models can reliably perform real-world software engineering tasks.

7. Conclusion
SWE-bench provides a rigorous benchmark for evaluating language models on real-world software engineering. Our results show that while current models have impressive code generation abilities, translating these to practical software engineering remains a major challenge. We release SWE-bench as an open resource to drive progress in this important direction.

References
[1] Chen et al. Evaluating Large Language Models Trained on Code. 2021.
[2] Austin et al. Program Synthesis with Large Language Models. 2021.
[3] Li et al. Competition-Level Code Generation with AlphaCode. 2022.
[4] Just et al. Defects4J: A Database of Existing Faults. 2014.
[5] Widyasari et al. BugsInPy: A Database of Existing Bugs in Python Programs. 2020.
""",
    },

    # ── Scenario 2: Long prose (~5,000 tokens) ──────────────────────
    {
        "id": "long-prose-rag",
        "title": "RAG Techniques Survey + Code Review Practices (Multi-Document Retrieval)",
        "category": "long-prose",
        "category_label": "Long Prose (~5,000 tok)",
        "description": "Simulates a RAG pipeline retrieving multiple documents. Many sentences are irrelevant to the query — ideal for testing input pruning at scale.",
        "authors": ["Survey Authors"],
        "query": "What are the most effective post-retrieval processing techniques for RAG pipelines?",
        "text": """Advanced RAG Techniques: A Survey of Retrieval-Augmented Generation

Abstract: Retrieval-Augmented Generation (RAG) has become a cornerstone technique for grounding large language model outputs in factual, up-to-date information. This survey provides a comprehensive overview of advanced RAG techniques, categorising them into pre-retrieval optimisation, retrieval strategies, post-retrieval processing, and generation enhancement methods.

1. Introduction
Large language models suffer from several well-known limitations: they can hallucinate facts, their knowledge is frozen at training time, and they lack access to private or domain-specific data. Retrieval-Augmented Generation addresses these limitations by combining a retrieval component with a generation component. When a user poses a query, the system first retrieves relevant documents from a knowledge base, then provides these documents as context to the language model for generating a response.

However, naive RAG implementations often produce suboptimal results. Retrieved documents may contain irrelevant information that distracts the model. The context window has limited capacity, forcing a trade-off between the amount of retrieved information and the space available for generation. Documents may be poorly chunked, losing important context. This survey examines techniques developed to address each of these challenges.

2. Pre-Retrieval Optimisation
Pre-retrieval techniques focus on improving what gets stored and how queries are formulated before any retrieval occurs.

2.1 Document Chunking Strategies
The way documents are split into chunks significantly impacts retrieval quality. Fixed-size chunking (e.g., 512 tokens with 50-token overlap) is simple but can split sentences mid-thought. Semantic chunking uses embedding similarity to find natural breakpoints. Hierarchical chunking creates chunks at multiple granularities, allowing retrieval at the appropriate level of detail.

2.2 Query Transformation
Raw user queries are often ambiguous or incomplete. Query expansion generates multiple reformulations. HyDE (Hypothetical Document Embeddings) generates a hypothetical answer and uses its embedding for retrieval. Step-back prompting first asks a more general question to establish context before the specific query.

2.3 Indexing Optimisation
Beyond simple vector stores, advanced indexing strategies include: multi-index approaches that maintain separate indices for summaries and full text, knowledge graph-augmented indices that capture entity relationships, and hybrid indices combining dense and sparse retrieval.

3. Retrieval Strategies
3.1 Hybrid Search
Combining dense retrieval (embedding similarity) with sparse retrieval (BM25/TF-IDF) often outperforms either alone. The Reciprocal Rank Fusion algorithm provides a simple way to merge ranked lists from different retrieval methods.

3.2 Multi-hop Retrieval
For complex queries requiring information from multiple documents, iterative retrieval performs multiple rounds. The model first retrieves initial documents, generates an intermediate response, then uses that response to formulate a follow-up query for additional retrieval.

3.3 Adaptive Retrieval
Not every query needs retrieval. Self-RAG trains the model to decide when to retrieve, what to retrieve, and whether the retrieved content is relevant. This reduces unnecessary retrieval calls and prevents the model from being distracted by irrelevant context.

4. Post-Retrieval Processing
4.1 Reranking
Initial retrieval casts a wide net. Reranking models (cross-encoders) score each query-document pair more accurately, allowing the system to keep only the most relevant passages. Popular rerankers include Cohere Rerank, BGE Reranker, and ColBERT.

4.2 Context Compression
Even after reranking, retrieved documents may contain redundant or irrelevant sections. Context compression techniques include:
- Extractive compression: Remove irrelevant sentences while keeping key passages intact
- Abstractive compression: Summarise documents before passing to the LLM
- Token-level pruning: Remove individual low-information tokens (e.g., LLMLingua)
- Sentence-level pruning: Score each sentence for relevance and drop below threshold

4.3 Document Augmentation
Retrieved passages can be augmented with metadata (source, date, confidence score), surrounding context from the original document, or related entities from a knowledge graph.

5. Generation Enhancement
5.1 Prompt Engineering for RAG
Effective RAG prompts clearly delineate retrieved context from the query, instruct the model to cite sources, and include instructions for handling cases where the context is insufficient.

5.2 Faithfulness and Attribution
Ensuring the model's response is grounded in the retrieved context requires: chain-of-thought reasoning that references specific passages, self-consistency checks that verify claims against the context, and citation generation that links each claim to its source document.

6. Conclusion
RAG has evolved from simple retrieve-and-generate pipelines to sophisticated systems with multiple optimisation points. The most effective implementations combine several of these techniques in a pipeline tailored to the specific use case and data characteristics.

--- RETRIEVED DOCUMENT 2 (lower relevance) ---

Automated Code Review with Large Language Models: Practices and Challenges

Abstract: Code review is a critical software engineering practice that improves code quality, shares knowledge, and catches bugs before they reach production. This paper examines the growing use of large language models for automated code review, analysing their strengths, limitations, and the practical considerations for integrating them into development workflows.

1. Introduction
Code review has been a cornerstone of software engineering since its formalisation by Fagan in 1976. In modern development, code reviews serve multiple purposes: catching defects, ensuring code style consistency, knowledge sharing among team members, and maintaining architectural integrity. Despite its importance, code review is time-consuming. Studies show that developers spend 5-15% of their working time on reviews, and review turnaround time is a frequent bottleneck in development velocity.

The emergence of large language models has sparked interest in automating parts of the code review process. Tools like GitHub Copilot, CodeRabbit, and various LLM-based review bots can now analyse code changes and provide feedback on potential issues, style violations, and improvement opportunities.

2. Taxonomy of LLM Code Review Capabilities

2.1 Bug Detection
LLMs can identify several classes of bugs in code changes: null pointer and undefined reference risks, resource leaks with unclosed files and connections, off-by-one errors in loops and array access, race conditions in concurrent code, and SQL injection and XSS vulnerabilities.

2.2 Style and Convention Enforcement
LLMs can detect violations of coding standards, naming conventions, and project-specific patterns. Unlike rule-based linters, they can understand semantic intent and suggest more idiomatic alternatives.

2.3 Documentation Quality
Models can assess whether code changes are adequately documented, suggest docstring improvements, and flag public API changes that lack documentation updates.

2.4 Performance Suggestions
LLMs can identify common performance anti-patterns such as string concatenation in loops, unnecessary object creation, and suboptimal algorithm choices.

3. Evaluation Results
We evaluated GPT-4, Claude 3, and Llama-3-70B on a dataset of 500 real code reviews from open-source projects. Key findings: (1) LLMs perform well on common bug patterns but struggle with project-specific logic. (2) False positive rates remain high enough to cause alert fatigue if not managed. (3) The models are most useful as a first pass that surfaces obvious issues, freeing human reviewers to focus on architectural and design concerns. (4) Smaller open-source models lag significantly behind proprietary models but are improving rapidly.

4. Practical Integration Patterns

4.1 Triage Mode
Use the LLM to categorise review comments by severity and type, allowing reviewers to prioritise their attention. Low-severity style issues can be auto-fixed, while high-severity logic issues require human review.

4.2 Context Window Management
Code reviews often involve large diffs. Effective LLM review requires careful context management: include the changed files, relevant test files, and referenced modules while staying within context limits. This is where context compression techniques become valuable — they can reduce the volume of context while preserving the information needed for accurate review.

5. Challenges and Limitations
Context limitations prevent holistic codebase understanding. Models lack runtime information and cannot execute code to verify suggestions. False positives erode developer trust over time. Security-sensitive code requires human review regardless of model confidence. Models may reinforce existing patterns rather than suggesting improvements.

6. Conclusion
LLM-based code review tools are a valuable addition to the developer toolkit but are not a replacement for human reviewers. The most effective approach combines automated first-pass review with focused human review, using context compression to manage the volume of information flowing through the pipeline.

--- RETRIEVED DOCUMENT 3 (noise/tangential) ---

A Brief History of Version Control Systems

Version control has evolved from manual file copying to sophisticated distributed systems. RCS (1982) introduced file-level locking. CVS (1990) added concurrent editing with merge. Subversion (2000) provided atomic commits and directory versioning. Git (2005), created by Linus Torvalds for Linux kernel development, introduced distributed version control with content-addressable storage, enabling each developer to have a complete repository clone.

Modern git workflows include GitFlow (feature branches with develop/release/main), GitHub Flow (simplified: feature branches merged to main), and trunk-based development (short-lived branches, frequent integration). The choice of workflow affects code review practices, merge conflict frequency, and deployment cadence.

Git's internal data model uses four object types: blobs (file contents), trees (directories), commits (snapshots with metadata), and tags (named references). The SHA-1 hash of each object's contents serves as its identifier, creating a content-addressable filesystem that enables efficient deduplication and integrity verification.
""",
    },

    # ── Scenario 3: JSON-heavy context (~2,500 tokens) ──────────────
    {
        "id": "json-heavy",
        "title": "Agent Tool Calls — API Responses with JSON Payloads",
        "category": "json-heavy",
        "category_label": "JSON-Heavy (~2,500 tok)",
        "description": "Simulates an LLM agent context filled with JSON tool-call responses. Tests structural compression of arrays, nested objects, and repeated schemas.",
        "authors": [],
        "query": "Based on the monitoring data, which service has the highest error rate and what is the likely root cause?",
        "text": """System monitoring context for production incident triage.

The following data was retrieved from our observability stack for the last 30 minutes.

=== Datadog Metrics Query Results ===

Service health summary (JSON from /api/v1/metrics):
{"services": [{"name": "api-gateway", "region": "us-east-1", "instances": 12, "cpu_avg": 45.2, "memory_avg": 67.8, "request_rate": 2340, "error_rate": 0.02, "p50_latency_ms": 12, "p95_latency_ms": 45, "p99_latency_ms": 120, "status": "healthy"}, {"name": "auth-service", "region": "us-east-1", "instances": 6, "cpu_avg": 78.9, "memory_avg": 82.1, "request_rate": 890, "error_rate": 0.15, "p50_latency_ms": 45, "p95_latency_ms": 890, "p99_latency_ms": 2300, "status": "degraded"}, {"name": "user-service", "region": "us-east-1", "instances": 8, "cpu_avg": 32.1, "memory_avg": 45.6, "request_rate": 1200, "error_rate": 0.01, "p50_latency_ms": 8, "p95_latency_ms": 25, "p99_latency_ms": 60, "status": "healthy"}, {"name": "payment-service", "region": "us-east-1", "instances": 4, "cpu_avg": 55.3, "memory_avg": 71.2, "request_rate": 450, "error_rate": 0.03, "p50_latency_ms": 23, "p95_latency_ms": 67, "p99_latency_ms": 150, "status": "healthy"}, {"name": "notification-service", "region": "us-east-1", "instances": 3, "cpu_avg": 22.4, "memory_avg": 38.9, "request_rate": 670, "error_rate": 0.005, "p50_latency_ms": 5, "p95_latency_ms": 15, "p99_latency_ms": 35, "status": "healthy"}, {"name": "search-service", "region": "us-east-1", "instances": 6, "cpu_avg": 88.7, "memory_avg": 91.3, "request_rate": 1800, "error_rate": 0.08, "p50_latency_ms": 120, "p95_latency_ms": 450, "p99_latency_ms": 1200, "status": "warning"}, {"name": "recommendation-engine", "region": "us-east-1", "instances": 4, "cpu_avg": 92.1, "memory_avg": 88.4, "request_rate": 340, "error_rate": 0.12, "p50_latency_ms": 200, "p95_latency_ms": 800, "p99_latency_ms": 3500, "status": "degraded"}, {"name": "cache-layer", "region": "us-east-1", "instances": 3, "cpu_avg": 15.6, "memory_avg": 78.2, "request_rate": 8900, "error_rate": 0.001, "p50_latency_ms": 1, "p95_latency_ms": 3, "p99_latency_ms": 8, "status": "healthy"}]}

=== Recent Error Logs (from Sentry) ===

[{"timestamp": "2026-09-22T12:45:23Z", "service": "auth-service", "level": "ERROR", "message": "Connection pool exhausted: max_connections=50 reached", "trace_id": "abc-123-def", "count_last_5min": 234}, {"timestamp": "2026-09-22T12:44:58Z", "service": "auth-service", "level": "ERROR", "message": "Redis timeout after 5000ms: ETIMEDOUT connecting to redis-cluster-01.internal:6379", "trace_id": "abc-124-def", "count_last_5min": 189}, {"timestamp": "2026-09-22T12:44:12Z", "service": "auth-service", "level": "WARN", "message": "Token validation fallback to database — cache miss rate 87%", "trace_id": "abc-125-def", "count_last_5min": 567}, {"timestamp": "2026-09-22T12:43:45Z", "service": "search-service", "level": "ERROR", "message": "Elasticsearch cluster health RED: 2 of 5 shards unassigned", "trace_id": "xyz-001-abc", "count_last_5min": 45}, {"timestamp": "2026-09-22T12:43:30Z", "service": "recommendation-engine", "level": "ERROR", "message": "Model inference timeout: TensorRT engine failed to respond within 3000ms", "trace_id": "rec-001-xyz", "count_last_5min": 78}, {"timestamp": "2026-09-22T12:42:15Z", "service": "recommendation-engine", "level": "WARN", "message": "GPU memory utilisation at 97.2% — OOM risk", "trace_id": "rec-002-xyz", "count_last_5min": 12}]

=== Infrastructure Status (from Terraform/CloudWatch) ===

{"cluster": "prod-eks-01", "node_count": 24, "nodes_ready": 24, "pod_total": 187, "pod_running": 183, "pod_pending": 4, "pending_pods": [{"name": "auth-service-7f8d9c-xk2mn", "reason": "Insufficient memory", "requested": "2Gi", "node_available": "512Mi"}, {"name": "auth-service-7f8d9c-lp4qr", "reason": "Insufficient memory", "requested": "2Gi", "node_available": "256Mi"}, {"name": "search-service-5a6b7c-mn8op", "reason": "Insufficient cpu", "requested": "4000m", "node_available": "1200m"}, {"name": "recommendation-engine-3d4e5f-qr2st", "reason": "Insufficient nvidia.com/gpu", "requested": "1", "node_available": "0"}], "recent_events": [{"type": "Warning", "reason": "FailedScheduling", "message": "0/24 nodes are available: 8 Insufficient memory, 4 Insufficient cpu, 12 node(s) had taint"}, {"type": "Normal", "reason": "ScaleUp", "message": "Auto-scaling group prod-gpu-nodes: scaling from 2 to 4 instances"}, {"type": "Warning", "reason": "OOMKilled", "message": "Container auth-service in pod auth-service-7f8d9c-ab1cd was OOMKilled (exit code 137)"}]}

=== Database Metrics (from RDS CloudWatch) ===

{"databases": [{"name": "prod-primary-pg", "engine": "PostgreSQL 16.2", "cpu": 34.5, "connections_active": 89, "connections_max": 200, "read_iops": 1200, "write_iops": 450, "replication_lag_ms": 12, "storage_used_gb": 456, "storage_total_gb": 1000}, {"name": "prod-replica-pg-01", "engine": "PostgreSQL 16.2", "cpu": 28.3, "connections_active": 67, "connections_max": 200, "read_iops": 2300, "write_iops": 0, "replication_lag_ms": 8, "storage_used_gb": 456, "storage_total_gb": 1000}, {"name": "prod-redis-cluster", "engine": "Redis 7.2", "cpu": 95.8, "connections_active": 1247, "connections_max": 1500, "memory_used_gb": 14.8, "memory_max_gb": 15.0, "eviction_rate": 892, "keyspace_hits": 45000, "keyspace_misses": 38000, "hit_rate": 0.542}]}
""",
    },

    # ── Scenario 4: Code-heavy context (~2,800 tokens) ──────────────
    {
        "id": "code-heavy",
        "title": "Code Review Context — Python Module with Tests and Config",
        "category": "code-heavy",
        "category_label": "Code-Heavy (~2,800 tok)",
        "description": "A code review diff with full file context, tests, and config. Tests code-aware compression (AST stripping, comment removal, whitespace).",
        "authors": [],
        "query": "Review this code change. Are there any bugs, performance issues, or missing error handling?",
        "text": '''Code review context for PR #1847: "Add rate limiting middleware to API gateway"

=== Changed File: src/middleware/rate_limiter.py ===

```python
"""Rate limiting middleware using sliding window algorithm.

Supports per-user and per-IP rate limiting with configurable windows
and limits. Uses Redis for distributed state across multiple instances.
"""

import time
import hashlib
import logging
from typing import Optional
from dataclasses import dataclass, field
from functools import wraps

import redis
from flask import request, jsonify, g

logger = logging.getLogger(__name__)

@dataclass
class RateLimitConfig:
    """Configuration for a rate limit rule."""
    requests_per_window: int = 100
    window_seconds: int = 60
    burst_multiplier: float = 1.5
    key_prefix: str = "rl"
    # Per-tier overrides
    tier_limits: dict = field(default_factory=lambda: {
        "free": 60,
        "basic": 300,
        "premium": 1000,
        "enterprise": 5000,
    })

class RateLimiter:
    """Sliding window rate limiter backed by Redis."""

    def __init__(self, redis_client: redis.Redis, config: RateLimitConfig = None):
        self.redis = redis_client
        self.config = config or RateLimitConfig()
        self._lua_script = self.redis.register_script(self.SLIDING_WINDOW_LUA)

    SLIDING_WINDOW_LUA = """
    local key = KEYS[1]
    local now = tonumber(ARGV[1])
    local window = tonumber(ARGV[2])
    local limit = tonumber(ARGV[3])

    -- Remove expired entries
    redis.call('ZREMRANGEBYSCORE', key, 0, now - window)

    -- Count current requests
    local count = redis.call('ZCARD', key)

    if count < limit then
        -- Add new request
        redis.call('ZADD', key, now, now .. '-' .. math.random(1000000))
        redis.call('EXPIRE', key, window)
        return {1, limit - count - 1, 0}  -- allowed, remaining, retry_after
    else
        -- Get oldest entry to calculate retry_after
        local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
        local retry_after = window - (now - tonumber(oldest[2]))
        return {0, 0, retry_after}  -- denied, remaining, retry_after
    end
    """

    def _get_key(self, identifier: str) -> str:
        """Generate a Redis key for the rate limit counter."""
        hashed = hashlib.md5(identifier.encode()).hexdigest()[:12]
        return f"{self.config.key_prefix}:{hashed}"

    def _get_limit_for_user(self, user_id: Optional[str] = None) -> int:
        """Look up the rate limit for a user based on their subscription tier."""
        if user_id is None:
            return self.config.requests_per_window

        # TODO: This hits the database on every request — should cache tier lookups
        from models.user import User
        user = User.query.get(user_id)
        if user and user.subscription_tier in self.config.tier_limits:
            return self.config.tier_limits[user.subscription_tier]
        return self.config.requests_per_window

    def check(self, identifier: str, user_id: Optional[str] = None) -> dict:
        """Check if a request should be allowed.

        Returns:
            dict with keys: allowed (bool), remaining (int), retry_after (int)
        """
        key = self._get_key(identifier)
        limit = self._get_limit_for_user(user_id)
        now = time.time()

        try:
            result = self._lua_script(
                keys=[key],
                args=[now, self.config.window_seconds, limit]
            )
            return {
                "allowed": bool(result[0]),
                "remaining": int(result[1]),
                "retry_after": int(result[2]),
                "limit": limit,
            }
        except redis.ConnectionError:
            # Fail open — allow request if Redis is down
            logger.warning("Redis connection failed — rate limit check skipped")
            return {"allowed": True, "remaining": -1, "retry_after": 0, "limit": limit}
        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            return {"allowed": True, "remaining": -1, "retry_after": 0, "limit": limit}

    def middleware(self):
        """Flask middleware that enforces rate limiting."""
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                # Determine identifier: authenticated user ID or IP address
                user_id = getattr(g, 'current_user_id', None)
                identifier = user_id or request.remote_addr

                result = self.check(identifier, user_id)

                if not result["allowed"]:
                    response = jsonify({
                        "error": "Rate limit exceeded",
                        "retry_after": result["retry_after"],
                    })
                    response.status_code = 429
                    response.headers["Retry-After"] = str(result["retry_after"])
                    response.headers["X-RateLimit-Limit"] = str(result["limit"])
                    response.headers["X-RateLimit-Remaining"] = "0"
                    return response

                # Set rate limit headers on successful requests too
                response = f(*args, **kwargs)
                response.headers["X-RateLimit-Limit"] = str(result["limit"])
                response.headers["X-RateLimit-Remaining"] = str(result["remaining"])
                return response

            return decorated_function
        return decorator
```

=== Test File: tests/test_rate_limiter.py ===

```python
import pytest
import time
from unittest.mock import MagicMock, patch
from middleware.rate_limiter import RateLimiter, RateLimitConfig

@pytest.fixture
def redis_mock():
    mock = MagicMock()
    mock.register_script.return_value = MagicMock()
    return mock

@pytest.fixture
def limiter(redis_mock):
    return RateLimiter(redis_mock, RateLimitConfig(requests_per_window=10))

class TestRateLimiter:
    def test_allows_under_limit(self, limiter):
        limiter._lua_script.return_value = [1, 9, 0]
        result = limiter.check("test-user")
        assert result["allowed"] is True
        assert result["remaining"] == 9

    def test_denies_over_limit(self, limiter):
        limiter._lua_script.return_value = [0, 0, 45]
        result = limiter.check("test-user")
        assert result["allowed"] is False
        assert result["retry_after"] == 45

    def test_fails_open_on_redis_error(self, limiter):
        limiter._lua_script.side_effect = Exception("Redis down")
        result = limiter.check("test-user")
        assert result["allowed"] is True

    def test_uses_tier_limit(self, limiter):
        with patch('middleware.rate_limiter.User') as MockUser:
            mock_user = MagicMock()
            mock_user.subscription_tier = "premium"
            MockUser.query.get.return_value = mock_user
            limit = limiter._get_limit_for_user("user-123")
            assert limit == 1000
```

=== Config File: config/rate_limits.yaml ===

```yaml
rate_limiting:
  enabled: true
  redis_url: "redis://redis-cluster-01.internal:6379/0"
  default_window_seconds: 60
  default_requests_per_window: 100
  burst_multiplier: 1.5

  # Endpoint-specific overrides
  endpoints:
    /api/v1/search:
      requests_per_window: 30
      window_seconds: 60
    /api/v1/generate:
      requests_per_window: 10
      window_seconds: 60
    /api/v1/bulk-export:
      requests_per_window: 5
      window_seconds: 300

  # IP-based allowlist (no rate limiting)
  allowlist:
    - "10.0.0.0/8"       # Internal services
    - "172.16.0.0/12"    # VPN range
```
''',
    },

    # ── Scenario 5: Mixed context (~3,500 tokens) ───────────────────
    {
        "id": "mixed-rag",
        "title": "Production Debugging Context — Logs + Metrics + Code + Docs",
        "category": "mixed",
        "category_label": "Mixed Content (~3,500 tok)",
        "description": "Real-world agent context: prose docs + error logs + JSON metrics + code snippet + table. The most realistic test for combined compaction.",
        "authors": [],
        "query": "Why are users experiencing slow login times and what should we fix first?",
        "text": """Context retrieved for incident investigation: slow user login times (P95 > 5s).

=== Runbook: Authentication Service ===

The authentication service handles all user login, token refresh, and session management. It is a critical-path service — every API request goes through auth token validation.

Architecture overview:
1. User submits credentials to /api/v1/auth/login
2. Auth service validates credentials against PostgreSQL (users table)
3. On success, generates a JWT token signed with RS256
4. Token is cached in Redis with a 15-minute TTL for fast validation
5. Subsequent requests validate tokens against Redis cache first, falling back to JWT signature verification if cache miss

Known scaling considerations:
- The JWT signing step uses RSA-2048 which is CPU-intensive (~2ms per sign)
- Redis cache is shared across all auth-service instances
- Database connection pool is capped at 50 connections per instance
- Token refresh requests are 3x more frequent than login requests during peak hours
- Session metadata writes are batched every 30 seconds to reduce DB load

Recent changes (last 7 days):
- Sept 15: Deployed v2.4.1 — added MFA support for enterprise accounts
- Sept 18: Increased connection pool from 30 to 50 per instance
- Sept 20: Redis cluster maintenance window (10 min downtime, 02:00-02:10 UTC)
- Sept 21: Scaled from 4 to 6 auth-service instances due to traffic increase

=== Error Logs (last 1 hour, filtered to auth-service) ===

[{"ts": "12:45:23", "level": "ERROR", "msg": "Connection pool exhausted: waited 4823ms for available connection", "pool_size": 50, "active": 50, "waiting": 23}, {"ts": "12:44:58", "level": "ERROR", "msg": "Redis ETIMEDOUT after 5000ms", "host": "redis-cluster-01.internal:6379", "retry": 2}, {"ts": "12:44:12", "level": "WARN", "msg": "Token validation cache miss — falling back to DB", "cache_hit_rate": "54.2%", "user_id": "usr_8f2a"}, {"ts": "12:43:45", "level": "ERROR", "msg": "Connection pool exhausted: waited 3211ms for available connection", "pool_size": 50, "active": 50, "waiting": 18}, {"ts": "12:42:30", "level": "WARN", "msg": "MFA verification slow: TOTP validation took 890ms", "user_id": "usr_enterprise_01"}, {"ts": "12:41:15", "level": "INFO", "msg": "Login request completed", "duration_ms": 5234, "breakdown": {"db_auth": 3100, "jwt_sign": 8, "redis_cache_write": 2100, "mfa_check": 0}}, {"ts": "12:40:02", "level": "INFO", "msg": "Login request completed", "duration_ms": 1823, "breakdown": {"db_auth": 45, "jwt_sign": 6, "redis_cache_write": 12, "mfa_check": 1760}}, {"ts": "12:39:45", "level": "ERROR", "msg": "Redis ETIMEDOUT after 5000ms", "host": "redis-cluster-01.internal:6379", "retry": 3}]

=== Current Metrics Snapshot ===

{"auth_service": {"instances": 6, "cpu_avg_pct": 78.9, "memory_avg_pct": 82.1, "request_rate_per_sec": 14.8, "error_rate_pct": 15.2, "p50_ms": 45, "p95_ms": 5200, "p99_ms": 8900}, "redis_cluster": {"cpu_pct": 95.8, "memory_used_gb": 14.8, "memory_max_gb": 15.0, "connections": 1247, "max_connections": 1500, "hit_rate_pct": 54.2, "eviction_rate_per_sec": 892, "commands_per_sec": 45000}, "postgres_primary": {"cpu_pct": 34.5, "active_connections": 89, "max_connections": 200, "avg_query_time_ms": 45, "slow_queries_count": 12, "lock_waits_count": 3}}

=== Related Code: Token Validation (current version) ===

```python
async def validate_token(token: str) -> Optional[User]:
    # Try Redis cache first
    cache_key = f"token:{hashlib.sha256(token.encode()).hexdigest()[:16]}"
    try:
        cached = await redis_client.get(cache_key, timeout=5.0)
        if cached:
            return User.from_cache(json.loads(cached))
    except asyncio.TimeoutError:
        logger.warning("Redis timeout during token validation")
    except Exception as e:
        logger.error(f"Redis error: {e}")

    # Fallback: verify JWT signature and load from DB
    try:
        payload = jwt.decode(token, PUBLIC_KEY, algorithms=["RS256"])
        user = await db.fetch_user(payload["sub"])
        if user:
            # Write-back to cache (fire-and-forget)
            asyncio.create_task(
                redis_client.setex(cache_key, 900, json.dumps(user.to_cache()))
            )
        return user
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
```

=== Deployment History ===

| Date | Version | Change | Impact |
|------|---------|--------|--------|
| Sept 15 | v2.4.1 | Added MFA support | +890ms for enterprise users with MFA enabled |
| Sept 18 | v2.4.2 | Increased DB pool 30→50 | Reduced pool exhaustion errors by 60% |
| Sept 20 | — | Redis maintenance (10min) | Brief cache invalidation, elevated DB load for ~2hrs after |
| Sept 21 | — | Scaled 4→6 instances | Reduced per-instance CPU from 92% to 79% |
| Sept 22 | — | No deployment | Current incident: P95 login > 5s |

=== On-Call Notes ===

"Redis cluster is under heavy memory pressure — 14.8/15GB with high eviction rate (892/sec). The cache hit rate has dropped from normal 95%+ to 54%. This means most token validations are falling through to the database, which is causing connection pool exhaustion. The root issue might be the combination of: (1) more instances = more Redis connections = less memory per connection, and (2) the MFA feature storing additional session data in Redis."
""",
    },
]


def save_scenarios() -> Path:
    """Save static scenarios to JSON."""
    for s in SCENARIOS:
        s["text_chars"] = len(s["text"])
        s["approx_tokens"] = max(1, len(s["text"]) // 4)

    with open(SCENARIOS_FILE, "w") as f:
        json.dump(SCENARIOS, f, indent=2, ensure_ascii=False)

    print(f"Saved {len(SCENARIOS)} scenarios to {SCENARIOS_FILE}")
    return SCENARIOS_FILE


def load_scenarios() -> list[dict]:
    """Load scenarios — generate from static data if file doesn't exist."""
    if not SCENARIOS_FILE.exists():
        save_scenarios()
    with open(SCENARIOS_FILE) as f:
        return json.load(f)


if __name__ == "__main__":
    save_scenarios()
    for s in SCENARIOS:
        tok = max(1, len(s["text"]) // 4)
        print(f"  [{s['category_label']:>25}] {s['id']}: {s['title'][:50]}... — ~{tok:,} tokens")
