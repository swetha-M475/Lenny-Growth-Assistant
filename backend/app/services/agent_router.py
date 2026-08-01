"""
Agent Router — Intent classification and skill routing.

Determines which skill to use based on user message analysis:
- Q&A Skill (default): Product/growth questions
- Ship30for30 Skill: Essay/article requests
- Artifact Skill: HTML/Markdown generation requests
"""

import logging
import re
from enum import Enum
from typing import AsyncGenerator, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.llm_service import llm_manager
from app.services.rag_service import format_context, retrieve_relevant_chunks
from app.skills.qa_skill import get_qa_system_prompt
from app.skills.ship30_skill import get_ship30_system_prompt
from app.skills.artifact_skill import get_artifact_system_prompt

logger = logging.getLogger(__name__)


class SkillType(str, Enum):
    QA = "qa"
    SHIP30FOR30 = "ship30for30"
    ARTIFACT = "artifact"


# Keywords/patterns for intent classification
SHIP30_KEYWORDS = [
    "ship30", "ship 30", "essay", "article", "write about",
    "write an essay", "write a piece", "write a post", "blog post",
    "atomic essay", "content piece", "newsletter", "write me",
    "draft an article", "compose", "ship30for30",
]

ARTIFACT_KEYWORDS = [
    "create a", "generate a", "build a", "make a",
    "html", "dashboard", "infographic", "visual",
    "component", "ui", "interface", "chart",
    "artifact", "template", "checklist", "framework document",
    "render", "design a", "mockup",
]


class AgentRouter:
    """Routes user messages to the appropriate skill based on intent."""

    def classify_intent(self, message: str, skill_hint: Optional[str] = None) -> SkillType:
        """
        Classify the user's intent into a skill type.
        
        Priority:
        1. Explicit skill_hint from the user
        2. Keyword/pattern matching
        3. Default to Q&A
        """
        # Explicit hint takes priority
        if skill_hint and skill_hint != "auto":
            try:
                return SkillType(skill_hint)
            except ValueError:
                pass

        msg_lower = message.lower()

        # Check for Ship30for30 intent
        for keyword in SHIP30_KEYWORDS:
            if keyword in msg_lower:
                logger.info(f"Classified intent as SHIP30FOR30 (matched: '{keyword}')")
                return SkillType.SHIP30FOR30

        # Check for Artifact intent
        for keyword in ARTIFACT_KEYWORDS:
            if keyword in msg_lower:
                # Further check: does it seem like a generation request?
                generation_verbs = ["create", "generate", "build", "make", "design", "render"]
                if any(verb in msg_lower for verb in generation_verbs):
                    logger.info(f"Classified intent as ARTIFACT (matched: '{keyword}')")
                    return SkillType.ARTIFACT

        # Default: Q&A
        logger.info("Classified intent as QA (default)")
        return SkillType.QA

    async def route(
        self,
        message: str,
        conversation_history: List[dict],
        db: AsyncSession,
        skill_hint: Optional[str] = None,
    ) -> tuple[SkillType, AsyncGenerator[str, None]]:
        """
        Route the message to the appropriate skill and return a streaming response.
        
        Returns:
            (skill_type, token_stream)
        """
        skill_type = self.classify_intent(message, skill_hint)

        # Retrieve relevant transcript chunks via RAG
        rag_chunks = await retrieve_relevant_chunks(message, db, top_k=6)
        context = format_context(rag_chunks)

        # Select system prompt based on skill
        if skill_type == SkillType.SHIP30FOR30:
            system_prompt = get_ship30_system_prompt(context)
        elif skill_type == SkillType.ARTIFACT:
            system_prompt = get_artifact_system_prompt(context)
        else:
            system_prompt = get_qa_system_prompt(context)

        # Build messages array with conversation history
        messages = []
        for msg in conversation_history[-10:]:  # Last 10 messages for context window
            messages.append({
                "role": msg["role"],
                "content": msg["content"],
            })
        messages.append({"role": "user", "content": message})

        # Get streaming response from LLM
        llm = llm_manager.get_llm()
        stream = llm.generate_stream(messages, system_prompt=system_prompt)

        return skill_type, stream


# Singleton router
agent_router = AgentRouter()
