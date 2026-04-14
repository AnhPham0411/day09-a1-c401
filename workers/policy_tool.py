"""
workers/policy_tool.py — Policy & Tool Worker
Sprint 2+3: Kiểm tra policy dựa vào context, gọi MCP tools khi cần.

Owner: Người 3 — Policy Enforcer

Input (từ AgentState):
    - task: câu hỏi
    - retrieved_chunks: context từ retrieval_worker
    - needs_tool: True nếu supervisor quyết định cần tool call

Output (vào AgentState):
    - policy_result: {"policy_applies", "policy_name", "exceptions_found", "source", "rule"}
    - mcp_tools_used: list of tool calls đã thực hiện
    - worker_io_log: log

Gọi độc lập để test:
    python workers/policy_tool.py
"""

import os
import sys
import re
from datetime import datetime
from typing import Optional, List, Dict, Any

WORKER_NAME = "policy_tool_worker"


# ─────────────────────────────────────────────
# MCP Client — Gọi tools từ mcp_server.py
# ─────────────────────────────────────────────

def _call_mcp_tool(tool_name: str, tool_input: dict) -> dict:
    """
    Gọi MCP tool qua dispatch_tool() từ mcp_server.py.

    Hỗ trợ các tools:
        - search_kb: tìm kiếm Knowledge Base
        - get_ticket_info: tra cứu thông tin ticket
        - check_access_permission: kiểm tra quyền truy cập
        - create_ticket: tạo ticket mới

    Returns:
        dict với keys: tool, input, output, error, timestamp
    """
    try:
        # Import mcp_server từ root project
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from mcp_server import dispatch_tool
        result = dispatch_tool(tool_name, tool_input)
        return {
            "tool": tool_name,
            "input": tool_input,
            "output": result,
            "error": None,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        return {
            "tool": tool_name,
            "input": tool_input,
            "output": None,
            "error": {"code": "MCP_CALL_FAILED", "reason": str(e)},
            "timestamp": datetime.now().isoformat(),
        }


def _discover_mcp_tools() -> list:
    """
    Discover available tools trên MCP server.
    Tương đương MCP protocol tools/list.
    """
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from mcp_server import list_tools
        return list_tools()
    except Exception as e:
        print(f"  ⚠️ MCP discovery failed: {e}")
        return []


# ─────────────────────────────────────────────
# Policy Analysis Logic — Rule-based + MCP
# ─────────────────────────────────────────────

def _detect_refund_exceptions(task: str, context_text: str) -> List[Dict]:
    """
    Phát hiện các ngoại lệ hoàn tiền theo policy_refund_v4.txt (Điều 3).

    Edge cases được handle:
        1. Flash Sale → không được hoàn tiền
        2. Digital product (license key, subscription) → không được hoàn tiền
        3. Sản phẩm đã kích hoạt / đã đăng ký → không được hoàn tiền
        4. Đã sử dụng / mở seal → không được hoàn tiền
    """
    task_lower = task.lower()
    combined = f"{task_lower} {context_text}"
    exceptions = []

    # Exception 1: Flash Sale
    if "flash sale" in combined:
        exceptions.append({
            "type": "flash_sale_exception",
            "rule": "Đơn hàng đã áp dụng mã giảm giá đặc biệt theo chương trình khuyến mãi Flash Sale không được hoàn tiền (Điều 3, chính sách hoàn tiền v4).",
            "source": "policy_refund_v4.txt",
            "severity": "blocking",
        })

    # Exception 2: Digital product / license key / subscription
    digital_keywords = ["license key", "license", "subscription", "kỹ thuật số",
                        "digital product", "sản phẩm số", "phần mềm"]
    if any(kw in combined for kw in digital_keywords):
        exceptions.append({
            "type": "digital_product_exception",
            "rule": "Sản phẩm thuộc danh mục hàng kỹ thuật số (license key, subscription) không được hoàn tiền (Điều 3, chính sách hoàn tiền v4).",
            "source": "policy_refund_v4.txt",
            "severity": "blocking",
        })

    # Exception 3: Sản phẩm đã kích hoạt / đăng ký tài khoản
    activated_keywords = ["đã kích hoạt", "đã đăng ký", "đã sử dụng",
                          "đã dùng", "đã mở seal", "activated", "used"]
    if any(kw in combined for kw in activated_keywords):
        exceptions.append({
            "type": "activated_exception",
            "rule": "Sản phẩm đã được kích hoạt hoặc đăng ký tài khoản không được hoàn tiền (Điều 3, chính sách hoàn tiền v4).",
            "source": "policy_refund_v4.txt",
            "severity": "blocking",
        })

    return exceptions


def _check_temporal_scoping(task: str) -> Optional[str]:
    """
    Kiểm tra temporal scoping — đơn hàng trước 01/02/2026 áp dụng policy v3.

    Các pattern detect:
        - "31/01/2026", "30/01", "trước 01/02", "trước ngày 1/2"
        - "tháng 1/2026", "january 2026"
    """
    task_lower = task.lower()

    # Detect date patterns trước effective date (01/02/2026)
    pre_v4_patterns = [
        r"31/01", r"30/01", r"29/01", r"28/01",
        r"trước 01/02", r"trước ngày 1/2", r"trước 1/2/2026",
        r"tháng 1/2026", r"tháng 01/2026", r"january 2026",
    ]

    for pattern in pre_v4_patterns:
        if re.search(pattern, task_lower):
            return (
                "Đơn hàng đặt trước 01/02/2026 áp dụng chính sách hoàn tiền phiên bản 3 (v3), "
                "không phải v4 hiện hành. Tài liệu hiện tại chỉ có chính sách v4. "
                "Cần xác nhận với CS Team về nội dung chính sách v3."
            )
    return None


def _check_refund_eligibility(task: str, context_text: str) -> Dict:
    """
    Kiểm tra tổng thể điều kiện hoàn tiền theo Điều 2.

    Conditions (tất cả phải đáp ứng):
        1. Sản phẩm bị lỗi do nhà sản xuất
        2. Yêu cầu trong 7 ngày làm việc
        3. Đơn hàng chưa sử dụng / chưa mở seal
    """
    combined = f"{task.lower()} {context_text}"
    conditions_met = []
    conditions_unclear = []

    # Check: lỗi nhà sản xuất
    if any(kw in combined for kw in ["lỗi nhà sản xuất", "lỗi sản xuất", "manufacturing defect",
                                      "lỗi do nhà sản xuất", "sản phẩm lỗi"]):
        conditions_met.append("Sản phẩm bị lỗi do nhà sản xuất ✓")
    else:
        conditions_unclear.append("Chưa xác nhận: Sản phẩm có bị lỗi do nhà sản xuất hay không")

    # Check: trong 7 ngày
    day_match = re.search(r"(\d+)\s*ngày", combined)
    if day_match:
        days = int(day_match.group(1))
        if days <= 7:
            conditions_met.append(f"Yêu cầu trong {days} ngày (≤ 7 ngày) ✓")
        else:
            conditions_met.append(f"Yêu cầu sau {days} ngày (> 7 ngày) ✗ — quá hạn")

    # Check: chưa sử dụng
    if any(kw in combined for kw in ["chưa kích hoạt", "chưa dùng", "chưa sử dụng",
                                      "chưa mở seal", "unopened"]):
        conditions_met.append("Đơn hàng chưa sử dụng / chưa mở seal ✓")

    return {
        "conditions_met": conditions_met,
        "conditions_unclear": conditions_unclear,
    }


def _detect_access_control_need(task: str) -> Optional[Dict]:
    """
    Phát hiện nhu cầu kiểm tra quyền truy cập (access control).

    Returns dict với access_level và is_emergency, hoặc None.
    """
    task_lower = task.lower()

    access_level = None
    is_emergency = False

    # Detect access level
    if any(kw in task_lower for kw in ["level 1", "level1", "read only"]):
        access_level = 1
    elif any(kw in task_lower for kw in ["level 2", "level2", "standard access"]):
        access_level = 2
    elif any(kw in task_lower for kw in ["level 3", "level3", "elevated access", "admin access"]):
        access_level = 3
    elif any(kw in task_lower for kw in ["cấp quyền", "access", "quyền truy cập"]):
        # Generic access request — cần thêm context
        access_level = None  # sẽ xác định ở bước phân tích sâu hơn

    # Detect emergency
    if any(kw in task_lower for kw in ["khẩn cấp", "emergency", "p1", "urgent",
                                        "khẩn", "gấp", "critical"]):
        is_emergency = True

    # Detect requester role
    requester_role = "employee"  # default
    if "contractor" in task_lower:
        requester_role = "contractor"
    elif "manager" in task_lower:
        requester_role = "manager"
    elif "team lead" in task_lower or "senior" in task_lower:
        requester_role = "team_lead"

    if access_level is not None or any(kw in task_lower for kw in ["cấp quyền", "access level"]):
        return {
            "access_level": access_level,
            "is_emergency": is_emergency,
            "requester_role": requester_role,
        }

    return None


def _detect_p1_context(task: str) -> bool:
    """Phát hiện ngữ cảnh P1 khẩn cấp."""
    task_lower = task.lower()
    return any(kw in task_lower for kw in ["p1", "sự cố", "incident", "critical",
                                            "2am", "02:00", "khẩn cấp urgent"])


def analyze_policy(task: str, chunks: list) -> dict:
    """
    Phân tích policy dựa trên task và context chunks.

    Logic:
    1. Detect refund exceptions (Flash Sale, Digital, Activated)
    2. Check temporal scoping (v3 vs v4)
    3. Check refund eligibility conditions
    4. Detect access control needs
    5. Check P1/emergency context

    Returns:
        dict with: policy_applies, policy_name, exceptions_found, source,
                   policy_version_note, eligibility, access_check, explanation
    """
    task_lower = task.lower()
    context_text = " ".join([c.get("text", "") for c in chunks]).lower()

    # --- 1. Exception detection ---
    exceptions_found = _detect_refund_exceptions(task, context_text)

    # --- 2. Temporal scoping ---
    policy_version_note = _check_temporal_scoping(task) or ""

    # --- 3. Refund eligibility ---
    eligibility = {}
    is_refund_question = any(kw in task_lower for kw in [
        "hoàn tiền", "refund", "trả tiền", "trả lại", "store credit"
    ])
    if is_refund_question:
        eligibility = _check_refund_eligibility(task, context_text)

    # --- 4. Store credit detection ---
    store_credit_info = ""
    if "store credit" in task_lower or "credit nội bộ" in task_lower:
        store_credit_info = (
            "Khách hàng có thể chọn nhận store credit thay thế "
            "với giá trị 110% so với số tiền hoàn (Điều 5, policy v4)."
        )

    # --- 5. Determine policy_applies ---
    blocking_exceptions = [e for e in exceptions_found if e.get("severity") == "blocking"]
    policy_applies = len(blocking_exceptions) == 0

    # Nếu temporal scoping issue → flag là uncertain
    if policy_version_note:
        policy_applies = None  # Uncertain — cần v3

    # --- 6. Policy name ---
    policy_name = "refund_policy_v4"
    if policy_version_note:
        policy_name = "refund_policy_v3 (cần xác nhận)"

    # --- Sources ---
    sources = list({c.get("source", "unknown") for c in chunks if c})
    if is_refund_question and "policy_refund_v4.txt" not in sources:
        sources.append("policy_refund_v4.txt")

    return {
        "policy_applies": policy_applies,
        "policy_name": policy_name,
        "exceptions_found": exceptions_found,
        "source": sources,
        "policy_version_note": policy_version_note,
        "eligibility": eligibility,
        "store_credit_info": store_credit_info,
        "explanation": (
            f"Rule-based policy check: {len(exceptions_found)} exceptions detected. "
            f"Temporal scoping: {'flagged' if policy_version_note else 'OK'}."
        ),
    }


# ─────────────────────────────────────────────
# Worker Entry Point
# ─────────────────────────────────────────────

def run(state: dict) -> dict:
    """
    Worker entry point — gọi từ graph.py.

    Flow:
    1. Nếu chưa có chunks và needs_tool → gọi MCP search_kb
    2. Phân tích policy (refund exceptions, temporal scoping, eligibility)
    3. Nếu liên quan access control → gọi MCP check_access_permission
    4. Nếu liên quan ticket P1 → gọi MCP get_ticket_info
    5. Ghi trace: policy_result, mcp_tools_used, worker_io_logs

    Args:
        state: AgentState dict

    Returns:
        Updated AgentState với policy_result và mcp_tools_used
    """
    task = state.get("task", "")
    chunks = state.get("retrieved_chunks", [])
    needs_tool = state.get("needs_tool", False)

    state.setdefault("workers_called", [])
    state.setdefault("history", [])
    state.setdefault("mcp_tools_used", [])

    state["workers_called"].append(WORKER_NAME)

    worker_io = {
        "worker": WORKER_NAME,
        "input": {
            "task": task,
            "chunks_count": len(chunks),
            "needs_tool": needs_tool,
        },
        "output": None,
        "error": None,
    }

    try:
        # ── Step 1: Nếu chưa có chunks, gọi MCP search_kb để lấy context ──
        if not chunks and needs_tool:
            mcp_result = _call_mcp_tool("search_kb", {"query": task, "top_k": 3})
            state["mcp_tools_used"].append(mcp_result)
            state["history"].append(f"[{WORKER_NAME}] called MCP search_kb for context")

            if mcp_result.get("output") and mcp_result["output"].get("chunks"):
                chunks = mcp_result["output"]["chunks"]
                state["retrieved_chunks"] = chunks
                state["retrieved_sources"] = mcp_result["output"].get("sources", [])

        # ── Step 2: Phân tích policy chính ──
        policy_result = analyze_policy(task, chunks)
        state["policy_result"] = policy_result

        # ── Step 3: Nếu liên quan access control → gọi MCP check_access_permission ──
        access_need = _detect_access_control_need(task)
        if access_need and needs_tool:
            access_level = access_need.get("access_level")
            if access_level is not None:
                mcp_result = _call_mcp_tool("check_access_permission", {
                    "access_level": access_level,
                    "requester_role": access_need.get("requester_role", "employee"),
                    "is_emergency": access_need.get("is_emergency", False),
                })
                state["mcp_tools_used"].append(mcp_result)
                state["history"].append(
                    f"[{WORKER_NAME}] called MCP check_access_permission "
                    f"(level={access_level}, emergency={access_need.get('is_emergency')})"
                )

                # Merge access control result vào policy_result
                if mcp_result.get("output") and not mcp_result["output"].get("error"):
                    policy_result["access_control"] = mcp_result["output"]
                    state["policy_result"] = policy_result

        # ── Step 4: Nếu liên quan ticket P1/sự cố → gọi MCP get_ticket_info ──
        if needs_tool and _detect_p1_context(task):
            mcp_result = _call_mcp_tool("get_ticket_info", {"ticket_id": "P1-LATEST"})
            state["mcp_tools_used"].append(mcp_result)
            state["history"].append(f"[{WORKER_NAME}] called MCP get_ticket_info (P1-LATEST)")

            # Enrich policy result với ticket context
            if mcp_result.get("output") and not mcp_result["output"].get("error"):
                policy_result["ticket_context"] = {
                    "ticket_id": mcp_result["output"].get("ticket_id"),
                    "priority": mcp_result["output"].get("priority"),
                    "status": mcp_result["output"].get("status"),
                    "sla_deadline": mcp_result["output"].get("sla_deadline"),
                    "escalated": mcp_result["output"].get("escalated", False),
                    "notifications_sent": mcp_result["output"].get("notifications_sent", []),
                }
                state["policy_result"] = policy_result

        # ── Step 5: Build worker IO output cho trace ──
        worker_io["output"] = {
            "policy_applies": policy_result["policy_applies"],
            "exceptions_count": len(policy_result.get("exceptions_found", [])),
            "has_temporal_scoping": bool(policy_result.get("policy_version_note")),
            "has_access_control": "access_control" in policy_result,
            "has_ticket_context": "ticket_context" in policy_result,
            "mcp_calls_count": len(state["mcp_tools_used"]),
        }
        state["history"].append(
            f"[{WORKER_NAME}] policy_applies={policy_result['policy_applies']}, "
            f"exceptions={len(policy_result.get('exceptions_found', []))}, "
            f"mcp_calls={len(state['mcp_tools_used'])}"
        )

    except Exception as e:
        worker_io["error"] = {"code": "POLICY_CHECK_FAILED", "reason": str(e)}
        state["policy_result"] = {"error": str(e)}
        state["history"].append(f"[{WORKER_NAME}] ERROR: {e}")

    state.setdefault("worker_io_logs", []).append(worker_io)
    return state


# ─────────────────────────────────────────────
# Test độc lập — Comprehensive Edge Cases
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("Policy Tool Worker — Standalone Test (Người 3)")
    print("=" * 60)

    # ── Test 1: Flash Sale exception ──
    print("\n" + "─" * 50)
    print("TEST 1: Flash Sale — phải bị chặn hoàn tiền")
    print("─" * 50)
    tc1 = {
        "task": "Khách hàng Flash Sale yêu cầu hoàn tiền vì sản phẩm lỗi — được không?",
        "retrieved_chunks": [
            {"text": "Ngoại lệ không được hoàn tiền: Đơn hàng đã áp dụng mã giảm giá đặc biệt theo chương trình khuyến mãi Flash Sale.",
             "source": "policy_refund_v4.txt", "score": 0.9}
        ],
        "needs_tool": True,
    }
    r1 = run(tc1.copy())
    pr1 = r1.get("policy_result", {})
    print(f"  policy_applies: {pr1.get('policy_applies')}")
    assert pr1.get("policy_applies") == False, "❌ Flash Sale should NOT be refundable"
    print(f"  exceptions: {[e['type'] for e in pr1.get('exceptions_found', [])]}")
    assert any(e["type"] == "flash_sale_exception" for e in pr1.get("exceptions_found", [])), \
        "❌ Should detect flash_sale_exception"
    print("  ✅ PASS")

    # ── Test 2: Digital product (license key) ──
    print("\n" + "─" * 50)
    print("TEST 2: Digital Product (License Key) — phải bị chặn")
    print("─" * 50)
    tc2 = {
        "task": "Khách hàng muốn hoàn tiền license key đã kích hoạt.",
        "retrieved_chunks": [
            {"text": "Sản phẩm kỹ thuật số (license key, subscription) không được hoàn tiền (Điều 3).",
             "source": "policy_refund_v4.txt", "score": 0.88}
        ],
        "needs_tool": False,
    }
    r2 = run(tc2.copy())
    pr2 = r2.get("policy_result", {})
    print(f"  policy_applies: {pr2.get('policy_applies')}")
    assert pr2.get("policy_applies") == False, "❌ Digital product should NOT be refundable"
    exc_types = [e["type"] for e in pr2.get("exceptions_found", [])]
    print(f"  exceptions: {exc_types}")
    assert "digital_product_exception" in exc_types, "❌ Should detect digital_product_exception"
    assert "activated_exception" in exc_types, "❌ Should detect activated_exception"
    print("  ✅ PASS")

    # ── Test 3: Eligible refund — no exceptions ──
    print("\n" + "─" * 50)
    print("TEST 3: Eligible Refund — không có ngoại lệ")
    print("─" * 50)
    tc3 = {
        "task": "Khách hàng yêu cầu hoàn tiền trong 5 ngày, sản phẩm lỗi nhà sản xuất, chưa kích hoạt.",
        "retrieved_chunks": [
            {"text": "Yêu cầu trong 7 ngày làm việc, sản phẩm lỗi nhà sản xuất, chưa dùng.",
             "source": "policy_refund_v4.txt", "score": 0.85}
        ],
        "needs_tool": False,
    }
    r3 = run(tc3.copy())
    pr3 = r3.get("policy_result", {})
    print(f"  policy_applies: {pr3.get('policy_applies')}")
    assert pr3.get("policy_applies") == True, "❌ Should be eligible for refund"
    print(f"  eligibility: {pr3.get('eligibility', {}).get('conditions_met', [])}")
    print("  ✅ PASS")

    # ── Test 4: Temporal scoping — đơn trước 01/02/2026 ──
    print("\n" + "─" * 50)
    print("TEST 4: Temporal Scoping — đơn 31/01/2026")
    print("─" * 50)
    tc4 = {
        "task": "Khách hàng đặt đơn ngày 31/01/2026 và yêu cầu hoàn tiền ngày 07/02/2026. Sản phẩm lỗi nhà sản xuất, chưa kích hoạt, không phải Flash Sale. Được hoàn tiền không?",
        "retrieved_chunks": [
            {"text": "Chính sách này áp dụng cho tất cả các đơn hàng kể từ ngày 01/02/2026. Đơn trước ngày có hiệu lực áp dụng chính sách v3.",
             "source": "policy_refund_v4.txt", "score": 0.87}
        ],
        "needs_tool": False,
    }
    r4 = run(tc4.copy())
    pr4 = r4.get("policy_result", {})
    print(f"  policy_applies: {pr4.get('policy_applies')}")
    assert pr4.get("policy_applies") is None, "❌ Should be uncertain (v3 needed)"
    print(f"  version_note: {pr4.get('policy_version_note', '')[:80]}...")
    assert "v3" in pr4.get("policy_version_note", "").lower(), "❌ Should mention v3"
    print("  ✅ PASS")

    # ── Test 5: P1 urgent + access control ──
    print("\n" + "─" * 50)
    print("TEST 5: P1 Urgent + Access Level 3 (emergency)")
    print("─" * 50)
    tc5 = {
        "task": "Contractor cần Admin Access (Level 3) để khắc phục sự cố P1 đang active. Quy trình cấp quyền tạm thời như thế nào?",
        "retrieved_chunks": [
            {"text": "Level 3 — Elevated Access: Phê duyệt: Line Manager + IT Admin + IT Security. Thời gian xử lý: 3 ngày làm việc.",
             "source": "access_control_sop.txt", "score": 0.91},
            {"text": "Level 3 KHÔNG có emergency bypass. Phải follow quy trình chuẩn.",
             "source": "access_control_sop.txt", "score": 0.85},
        ],
        "needs_tool": True,
    }
    r5 = run(tc5.copy())
    pr5 = r5.get("policy_result", {})
    print(f"  access_control: {pr5.get('access_control', 'not found')}")
    mcp_calls = r5.get("mcp_tools_used", [])
    mcp_tool_names = [m["tool"] for m in mcp_calls]
    print(f"  MCP tools called: {mcp_tool_names}")
    assert "check_access_permission" in mcp_tool_names, "❌ Should call check_access_permission"
    assert "get_ticket_info" in mcp_tool_names, "❌ Should call get_ticket_info for P1 context"
    print("  ✅ PASS")

    # ── Test 6: Flash Sale + lỗi nhà sản xuất + 7 ngày (gq10 scenario) ──
    print("\n" + "─" * 50)
    print("TEST 6: Flash Sale + lỗi NXS + 7 ngày (câu gq10)")
    print("─" * 50)
    tc6 = {
        "task": "Khách hàng mua Flash Sale, sản phẩm lỗi nhà sản xuất, yêu cầu hoàn tiền trong 7 ngày. Được hoàn tiền không?",
        "retrieved_chunks": [
            {"text": "Ngoại lệ: Đơn hàng Flash Sale không được hoàn tiền.",
             "source": "policy_refund_v4.txt", "score": 0.92},
            {"text": "Sản phẩm bị lỗi do nhà sản xuất, yêu cầu trong 7 ngày.",
             "source": "policy_refund_v4.txt", "score": 0.85},
        ],
        "needs_tool": False,
    }
    r6 = run(tc6.copy())
    pr6 = r6.get("policy_result", {})
    print(f"  policy_applies: {pr6.get('policy_applies')}")
    assert pr6.get("policy_applies") == False, "❌ Flash Sale exception should block even with valid conditions"
    exc_types = [e["type"] for e in pr6.get("exceptions_found", [])]
    print(f"  exceptions: {exc_types}")
    assert "flash_sale_exception" in exc_types, "❌ Must detect flash_sale_exception"
    print("  ✅ PASS")

    # ── Test 7: P1 lúc 2am + Level 2 emergency (gq09 scenario) ──
    print("\n" + "─" * 50)
    print("TEST 7: P1 lúc 2am + Level 2 emergency bypass (câu gq09)")
    print("─" * 50)
    tc7 = {
        "task": "Ticket P1 lúc 2am. Cần cấp Level 2 access tạm thời cho contractor để thực hiện emergency fix. Đồng thời cần notify stakeholders theo SLA. Nêu đủ cả hai quy trình.",
        "retrieved_chunks": [
            {"text": "Ticket P1: Phản hồi ban đầu 15 phút. Escalation: tự động escalate lên Senior Engineer nếu không phản hồi trong 10 phút. Thông báo: Slack #incident-p1, email incident@company.internal, PagerDuty on-call.",
             "source": "sla_p1_2026.txt", "score": 0.93},
            {"text": "Level 2 — Standard Access: Phê duyệt: Line Manager + IT Admin. Level 2 có thể cấp tạm thời với approval đồng thời.",
             "source": "access_control_sop.txt", "score": 0.88},
        ],
        "needs_tool": True,
    }
    r7 = run(tc7.copy())
    pr7 = r7.get("policy_result", {})
    mcp_calls7 = r7.get("mcp_tools_used", [])
    mcp_tool_names7 = [m["tool"] for m in mcp_calls7]
    print(f"  MCP tools called: {mcp_tool_names7}")
    assert "check_access_permission" in mcp_tool_names7, "❌ Should call check_access_permission"
    assert "get_ticket_info" in mcp_tool_names7, "❌ Should call get_ticket_info"
    ac = pr7.get("access_control", {})
    print(f"  access_control.emergency_override: {ac.get('emergency_override')}")
    print(f"  access_control.required_approvers: {ac.get('required_approvers')}")
    print(f"  ticket_context: {pr7.get('ticket_context', {}).get('ticket_id')}")
    print("  ✅ PASS")

    # ── Test 8: Store credit value ──
    print("\n" + "─" * 50)
    print("TEST 8: Store credit = 110%")
    print("─" * 50)
    tc8 = {
        "task": "Store credit khi hoàn tiền có giá trị bao nhiêu so với tiền gốc?",
        "retrieved_chunks": [
            {"text": "Hoàn tiền qua credit nội bộ (store credit): khách hàng có thể chọn nhận store credit thay thế với giá trị 110% so với số tiền hoàn.",
             "source": "policy_refund_v4.txt", "score": 0.90}
        ],
        "needs_tool": False,
    }
    r8 = run(tc8.copy())
    pr8 = r8.get("policy_result", {})
    print(f"  store_credit_info: {pr8.get('store_credit_info', '')[:80]}...")
    assert "110%" in pr8.get("store_credit_info", ""), "❌ Should mention 110%"
    print("  ✅ PASS")

    # ── Test 9: MCP tool discovery ──
    print("\n" + "─" * 50)
    print("TEST 9: MCP Tool Discovery")
    print("─" * 50)
    tools = _discover_mcp_tools()
    print(f"  Available MCP tools: {len(tools)}")
    for t in tools:
        print(f"    • {t['name']}: {t['description'][:50]}...")
    assert len(tools) >= 2, "❌ MCP server phải có ít nhất 2 tools"
    print("  ✅ PASS")

    # ── Summary ──
    print("\n" + "=" * 60)
    print("✅ All 9 tests passed — policy_tool_worker ready!")
    print("=" * 60)
    print("\nEdge cases covered:")
    print("  • Flash Sale exception (blocking)")
    print("  • Digital product / license key exception (blocking)")
    print("  • Activated product exception (blocking)")
    print("  • Temporal scoping (v3 vs v4)")
    print("  • P1 urgent context (MCP get_ticket_info)")
    print("  • Access control (MCP check_access_permission)")
    print("  • Flash Sale + valid conditions (exception still blocks)")
    print("  • Multi-hop P1 + Level 2 emergency bypass")
    print("  • Store credit (110%)")
    print("  • MCP tool discovery")
