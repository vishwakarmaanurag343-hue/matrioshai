import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.config import settings
from app.schemas.conversation import ChatRequest
from app.services.conversation_service import ConversationService
from app.llm.ollama import OllamaProvider

router = APIRouter(prefix="/chat", tags=["Chat"])

@router.post("")
async def chat_endpoint(req: ChatRequest, db: Session = Depends(get_db)):
    conv_service = ConversationService(db)
    
    # 1. Resolve or create conversation
    if not req.conversation_id:
        conv = conv_service.create_conversation(title=f"Chat: {req.prompt[:30]}...")
        conv_id = conv.id
    else:
        conv = conv_service.get_conversation(req.conversation_id)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        conv_id = conv.id

    # 2. Persist user message
    user_msg = conv_service.add_message(
        conversation_id=conv_id,
        role="user",
        content=req.prompt
    )

    # 2. Check for executive command (@CEO, @COO, @CFO, @CMO, @CTO, @5C)
    from app.executive.router import ExecutiveRouter
    from app.executive.service import ExecutiveService
    exec_role, is_5c, clean_prompt = ExecutiveRouter.parse_command(req.prompt)

    if exec_role or is_5c:
        exec_service = ExecutiveService(db)
        if is_5c:
            synthesis = await exec_service.run_5c_council(prompt=clean_prompt, conversation_id=conv_id)
            formatted_response = (
                f"### 5C EXECUTIVE COUNCIL SYNTHESIS\n\n"
                f"**Decision Summary:** {synthesis.summary}\n\n"
                f"**Final Recommendation:** {synthesis.final_recommendation}\n\n"
                f"**Agreements:**\n" + "\n".join(f"- {a}" for a in synthesis.agreements) + "\n\n"
                f"**Conflicts & Tradeoffs:**\n" + "\n".join(f"- {c}" for c in synthesis.conflicts) + "\n\n"
                f"**Critical Risks:**\n" + "\n".join(f"- {r}" for r in synthesis.critical_risks) + "\n\n"
                f"**Next Actions:**\n" + "\n".join(f"- {na}" for na in synthesis.next_actions)
            )
        else:
            role_resp = await exec_service.analyze_role(role=exec_role, prompt=clean_prompt, conversation_id=conv_id)
            formatted_response = (
                f"### {exec_role.value} ASSESSMENT\n\n"
                f"**Summary:** {role_resp.summary}\n\n"
                f"**Confidence:** {role_resp.confidence.value}" + (f" ({role_resp.confidence_reason})" if role_resp.confidence_reason else "") + "\n\n"
                f"**Key Findings:**\n" + "\n".join(f"- {kf}" for kf in role_resp.key_findings) + "\n\n"
                f"**Assumptions:**\n" + "\n".join(f"- {a}" for a in role_resp.assumptions) + "\n\n"
                f"**Risks:**\n" + "\n".join(f"- {r}" for r in role_resp.risks) + "\n\n"
                f"**Recommendations:**\n" + "\n".join(f"- {rec}" for rec in role_resp.recommendations)
            )

        asst_msg = conv_service.add_message(
            conversation_id=conv_id,
            role="assistant",
            content=formatted_response,
            model=settings.OLLAMA_MODEL
        )
        return {
            "conversation_id": conv_id,
            "user_message_id": user_msg.id,
            "assistant_message_id": asst_msg.id,
            "response": formatted_response,
            "is_executive": True
        }

    # 3. Assemble prompt context & LLM messages
    llm_messages = conv_service.build_llm_messages(conv_id, req.prompt)
    llm_provider = OllamaProvider()

    # Streaming mode
    if req.stream:
        async def event_generator():
            full_response_chunks = []
            yield f"data: {json.dumps({'type': 'init', 'conversation_id': conv_id, 'user_message_id': user_msg.id})}\n\n"
            
            async for chunk in llm_provider.stream_chat(llm_messages):
                full_response_chunks.append(chunk)
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
            
            final_text = "".join(full_response_chunks)
            asst_msg = conv_service.add_message(
                conversation_id=conv_id,
                role="assistant",
                content=final_text,
                model=settings.OLLAMA_MODEL
            )
            yield f"data: {json.dumps({'type': 'done', 'assistant_message_id': asst_msg.id, 'full_content': final_text})}\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    # Non-streaming mode
    try:
        assistant_reply = await llm_provider.chat(llm_messages)
    except RuntimeError as e:
        # Gracefully handle Ollama offline or missing model error
        assistant_reply = f"⚠️ {str(e)}"
    
    asst_msg = conv_service.add_message(
        conversation_id=conv_id,
        role="assistant",
        content=assistant_reply,
        model=settings.OLLAMA_MODEL
    )

    return {
        "conversation_id": conv_id,
        "user_message": user_msg,
        "assistant_message": asst_msg
    }
