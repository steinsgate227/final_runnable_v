import os
import re
import json
import shutil
import time
import random
import hashlib
import subprocess
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import requests

try:
    from z3 import Optimize, Bool, If, Sum, sat
except Exception:
    Optimize = None
    Bool = None
    If = None
    Sum = None
    sat = None

# ================================================================
# Global configuration
# ================================================================
BASE_DIR = Path(__file__).resolve().parent
IVERILOG_BIN = os.environ.get("IVERILOG_BIN", "iverilog")
VVP_BIN = os.environ.get("VVP_BIN", "vvp")
VCS_BIN = os.environ.get("VCS_BIN", "vcs")
VERILATOR_BIN = os.environ.get("VERILATOR_BIN", "verilator")
VCS_TIMESCALE = os.environ.get("VCS_TIMESCALE", "1ns/1ps")
GEMINI_GATEWAY_URL = "https://us.novaiapi.com/v1/chat/completions"
API_KEY = os.environ.get("LEMON_API_KEY", "")
MODEL_NAME = os.environ.get("RTL_REPAIR_MODEL", "gpt-4o-mini")
RESUME_MODE = os.environ.get("RESUME_MODE", "1") == "1"
MAX_API_RETRIES = int(os.environ.get("MAX_API_RETRIES", "8"))
REQUEST_TIMEOUT_SEC = int(os.environ.get("REQUEST_TIMEOUT_SEC", "300"))
SIM_TIMEOUT_CYCLES = int(os.environ.get("SIM_TIMEOUT_CYCLES", "2000"))
MAX_ROUNDS = int(os.environ.get("MAX_ROUNDS", "5"))
MAX_CANDIDATES_PER_ROUND = int(os.environ.get("MAX_CANDIDATES_PER_ROUND", "5"))
COUNTERFACTUAL_TOPK = int(os.environ.get("COUNTERFACTUAL_TOPK", "3"))
REANCHOR_PROGRESS_MARGIN = float(os.environ.get("REANCHOR_PROGRESS_MARGIN", "0.10"))
AGENT_MODEL_DIAGNOSIS = os.environ.get("AGENT_MODEL_DIAGNOSIS", MODEL_NAME)
AGENT_MODEL_PATCH = os.environ.get("AGENT_MODEL_PATCH", MODEL_NAME)
AGENT_MODEL_VALIDATOR = os.environ.get("AGENT_MODEL_VALIDATOR", MODEL_NAME)
EXPERIMENT_DIR = BASE_DIR / "benchmark_results_v5_strict"
PROMPT_LOG_DIR = EXPERIMENT_DIR / "prompt_logs"
KNOWLEDGE_DIR = EXPERIMENT_DIR / "knowledge_base"
CACHE_DIR = EXPERIMENT_DIR / "cache"

for p in [EXPERIMENT_DIR, PROMPT_LOG_DIR, KNOWLEDGE_DIR, CACHE_DIR]:
    p.mkdir(parents=True, exist_ok=True)

TB_TEMPLATE = r'''
`timescale 1ns/1ps
`ifndef CLK_PERIOD
  `define CLK_PERIOD 10
`endif
`ifndef SIM_TIMEOUT_CYCLES
  `define SIM_TIMEOUT_CYCLES 2000
`endif
`ifndef STOP_AFTER_CYCLE
  `define STOP_AFTER_CYCLE -1
`endif
`ifndef TB_MODE
  `define TB_MODE 0
`endif

module tb_top;
  reg clk;
  reg rst_n;
  integer timeout_counter;
  integer failure_count;
  integer testcase_id;
  integer cycle_counter;

  // ${SIGNAL_DECLARATIONS}
  // ${REFERENCE_MODEL_DECLARATIONS}
  // ${DUT_INSTANTIATION}
  // ${MONITOR_DECLARATIONS}
  // ${CHECKER_LOGIC}
  // ${TASK_DECLARATIONS}
  // ${SNAPSHOT_TASK}

  initial begin
    clk = 0;
    forever #(`CLK_PERIOD/2) clk = ~clk;
  end

  initial begin
    rst_n = 0;
    failure_count = 0;
    testcase_id = 0;
    cycle_counter = 0;
    #25 rst_n = 1;
  end

  task automatic checkpoint_save;
    begin
    end
  endtask

  function integer get_failure_count;
    begin
      get_failure_count = failure_count;
    end
  endfunction

  initial begin
    timeout_counter = 0;
    forever begin
      @(posedge clk);
      timeout_counter = timeout_counter + 1;
      if (rst_n === 1'b1)
        cycle_counter = cycle_counter + 1;
      if (`STOP_AFTER_CYCLE >= 0 && cycle_counter >= `STOP_AFTER_CYCLE) begin
        $display("[TB] [STOP] CYCLE=%0d", cycle_counter);
        $finish;
      end
      if (`TB_MODE != 2 && rst_n === 1'b1) begin
        emit_snapshot();
      end
      if (timeout_counter > `SIM_TIMEOUT_CYCLES) begin
        $display("[TB] [ERROR] TIME=%0d TYPE=SIM_TIMEOUT", $time);
        failure_count = failure_count + 1;
        $finish;
      end
    end
  end

  initial begin
    wait(rst_n === 1'b1);
    // ${STIMULUS_LOGIC}
    #50;
    $display("[TB] FINISH");
    $finish;
  end
endmodule
'''

FORBIDDEN_SYSTEM_TASK_PATTERNS = [
    r"\$fsdb\w*",
    r"\$dumpfile",
    r"\$dumpvars",
    r"\$vcdplus\w*",
    r"\$shm_\w*",
    r"\$strobe",
]


def clean_generated_verilog(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"```[a-zA-Z]*\n?", "", text).replace("```", "").strip()
    if "{" in text and "}" in text:
        try:
            start = text.find("{")
            end = text.rfind("}") + 1
            candidate = text[start:end]
            json.loads(candidate)
            return candidate
        except Exception:
            pass

    lines = []
    for line in text.splitlines():
        if any(re.search(pat, line, re.IGNORECASE) for pat in FORBIDDEN_SYSTEM_TASK_PATTERNS):
            continue
        lines.append(line)
    return "\n".join(lines).strip() + "\n"


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def strip_markdown_json_wrappers(content: str) -> str:
    content = content.strip()
    content = re.sub(r"^```json\s*", "", content, flags=re.IGNORECASE)
    content = re.sub(r"^```\s*", "", content)
    content = re.sub(r"\s*```$", "", content)
    return content.strip()


def safe_json_loads(text: str) -> Dict[str, Any]:
    text = strip_markdown_json_wrappers(text)
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except Exception:
        return {}


def sha1_text(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def line_edit_distance(old: str, new: str) -> int:
    old_lines = old.splitlines()
    new_lines = new.splitlines()
    delta = abs(len(old_lines) - len(new_lines))
    overlap = min(len(old_lines), len(new_lines))
    delta += sum(1 for i in range(overlap) if old_lines[i] != new_lines[i])
    return delta


def loc_count(text: str) -> int:
    return sum(1 for x in text.splitlines() if x.strip())


@dataclass
class PortInfo:
    direction: str
    name: str
    width: str = ""

    @property
    def decl_width(self) -> str:
        return f" {self.width}" if self.width else ""


@dataclass
class ModuleMetadata:
    module_name: str
    ports: List[PortInfo] = field(default_factory=list)
    clock_names: List[str] = field(default_factory=list)
    reset_names: List[str] = field(default_factory=list)

    @property
    def inputs(self) -> List[PortInfo]:
        return [p for p in self.ports if p.direction == "input"]

    @property
    def outputs(self) -> List[PortInfo]:
        return [p for p in self.ports if p.direction == "output"]


@dataclass
class TraceSnapshot:
    cycle: int
    testcase_id: int
    inputs: Dict[str, str] = field(default_factory=dict)
    outputs: Dict[str, str] = field(default_factory=dict)
    raw_line: str = ""


@dataclass
class FaultRecord:
    t_err: int = 0
    input_repr: str = "N/A"
    expected_repr: str = "N/A"
    actual_repr: str = "N/A"
    signal: str = "N/A"
    assertion: str = "N/A"
    raw_line: str = ""
    window_start: int = 0
    window_end: int = 0
    window_k: int = 0
    family: str = "generic"
    testcase_id: int = -1


@dataclass
class TwinPair:
    failing_input: str = "N/A"
    passing_input: str = "N/A"
    expected_output: str = "N/A"
    actual_output: str = "N/A"
    hamming_distance: int = 0
    evidence: str = ""
    twin_cycle: int = -1
    twin_testcase_id: int = -1


@dataclass
class StructuredFaultEvidence:
    failing_case: Dict[str, Any]
    passing_twin: Dict[str, Any]
    earliest_failure_cycle: int
    first_assertion: str
    failure_signals: List[str]
    local_window: Dict[str, int]
    local_signal_cone: List[str]
    divergent_snapshots: List[Dict[str, Any]] = field(default_factory=list)
    feedback_context: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class DiagnosisReport:
    error_pattern: str
    confidence: float
    difference_analysis: str
    root_cause: str
    fix_action: str
    location: str
    candidate_locations: List[Dict[str, Any]] = field(default_factory=list)
    signal_layers: Dict[str, List[str]] = field(default_factory=dict)
    constraints: List[str] = field(default_factory=list)
    evidence_refs: List[str] = field(default_factory=list)
    recommended_action: str = ""
    edit_scope: List[str] = field(default_factory=list)


@dataclass
class FeedbackPackage:
    round_id: int
    failed_stage: str
    triggering_tests: List[int]
    first_failed_assertion: str
    failure_cycle: int
    divergent_signals: List[str]
    failed_patch_id: str
    diagnosis_summary: str
    validator_excerpt: str


@dataclass
class FailureSurfaceState:
    round_id: int
    earliest_failure_cycle: int
    failing_assertion: str
    failing_signal: str
    local_window_k: int
    local_error_count: int
    regressions: int = 0
    simplification_score: float = 0.0
    note: str = ""


@dataclass
class PatchCandidate:
    source: str
    patch_id: str
    code: str
    edit_distance: int
    syntax_ok: bool = False
    static_ok: bool = False
    local_pass: bool = False
    module_pass: bool = False
    full_pass: bool = False
    synth_ok: bool = False
    correctness_score: float = 0.0
    minimality_score: float = 0.0
    synthesizability_score: float = 0.0
    readability_score: float = 0.0
    q_score: float = 0.0
    note: str = ""
    stage_logs: Dict[str, str] = field(default_factory=dict)


class VerilogParser:
    SIMPLE_PORT_RE = re.compile(
        r"\b(input|output)\b\s*(?:reg|wire|logic\b)?\s*(\[[^\]]+\])?\s*([A-Za-z_][A-Za-z0-9_]*)",
        re.MULTILINE,
    )

    @classmethod
    def parse_interface(cls, file_path: Path) -> ModuleMetadata:
        source = read_text(file_path)
        module_match = re.search(r"\bmodule\s+([A-Za-z_][A-Za-z0-9_]*)", source)
        module_name = module_match.group(1) if module_match else "unknown"
        ports = [PortInfo(direction=d, width=w or "", name=n) for d, w, n in cls.SIMPLE_PORT_RE.findall(source)]
        clock_names = [p.name for p in ports if p.name.lower() in {"clk", "clock", "clk_i"}]
        reset_names = [p.name for p in ports if p.name.lower() in {"rst", "rst_n", "reset", "reset_n"}]
        return ModuleMetadata(module_name=module_name, ports=ports, clock_names=clock_names, reset_names=reset_names)


class LLMClient:
    @staticmethod
    def _log_prompt(task: str, filename: str, payload: Dict[str, Any], response_text: str) -> None:
        stamp = int(time.time() * 1000)
        base = PROMPT_LOG_DIR / f"{Path(filename).stem}_{task}_{stamp}"
        write_text(base.with_suffix(".request.json"), json.dumps(payload, indent=2, ensure_ascii=False))
        write_text(base.with_suffix(".response.txt"), response_text)

    @classmethod
    def call(cls, prompt: str, filename: str, task: str, expect_json: bool = False, model_name: Optional[str] = None) -> Dict[str, Any]:
        if not API_KEY:
            return {}
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
        }
        payload = {
            "model": model_name or MODEL_NAME,
            "messages": [
                {"role": "system", "content": "You are an expert Verilog repair assistant. Always obey formatting instructions exactly."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.0,
            "stream": False,
        }
        for attempt in range(1, MAX_API_RETRIES + 1):
            try:
                # 鏄捐憲澧炲姞 TB 鐢熸垚鐨勮秴鏃讹紝浠ュ簲瀵逛腑杞摼璺欢杩?                timeout = 450 if task in {"SYNTHESIZE", "RAG_PATCH", "TB_FILL_FULL"} else REQUEST_TIMEOUT_SEC
                resp = requests.post(GEMINI_GATEWAY_URL, headers=headers, json=payload, timeout=timeout)
                if resp.status_code == 429:
                    time.sleep(min(30, 4 * attempt) + random.uniform(0, 1.5))
                    continue
                if resp.status_code in (500, 502, 503, 504):
                    time.sleep(min(20, 3 * attempt))
                    continue
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                cls._log_prompt(task, filename, payload, content)
                if expect_json:
                    return safe_json_loads(content)
                return {"raw_content": content}
            except Exception:
                if attempt == MAX_API_RETRIES:
                    break
                time.sleep(min(10, attempt + 1))
        return {}


class KnowledgeBase:
    def __init__(self, root: Path):
        self.root = root
        self.cases_path = root / "cases.jsonl"
        if not self.cases_path.exists():
            write_text(self.cases_path, "")

    def add_case(self, family: str, diagnosis: DiagnosisReport, patch: PatchCandidate, evidence: StructuredFaultEvidence) -> None:
        record = {
            "family": family,
            "error_pattern": diagnosis.error_pattern,
            "fix_action": diagnosis.fix_action,
            "location": diagnosis.location,
            "fault_signal": ",".join(evidence.failure_signals),
            "patch_id": patch.patch_id,
            "source": patch.source,
            "note": patch.note,
            "q_score": patch.q_score,
            "code_hash": sha1_text(patch.code),
            "code_excerpt": "\n".join(patch.code.splitlines()[:120]),
        }
        with self.cases_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def retrieve(self, family: str, diagnosis: DiagnosisReport, limit: int = 5) -> List[Dict[str, Any]]:
        rows = []
        for line in self.cases_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
        scored = []
        for row in rows:
            score = 0.0
            if row.get("family") == family:
                score += 0.5
            if row.get("error_pattern") == diagnosis.error_pattern:
                score += 0.25
            if diagnosis.location and row.get("location") == diagnosis.location:
                score += 0.15
            if diagnosis.fix_action and diagnosis.fix_action == row.get("fix_action"):
                score += 0.10
            scored.append((score, row))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [r for s, r in scored[:limit] if s > 0]


class Validator:
    def __init__(self, sandbox: Path, dut_path: Path, tb_path: Path):
        self.sandbox = sandbox
        self.dut_path = dut_path
        self.tb_path = tb_path
        self.analyze_log = sandbox / "analyze.log"
        self.vcs_log = sandbox / "vcs.log"
        self.sim_log = sandbox / "sim.log"
        self.verilator_log = sandbox / "verilator.log"
        self.simv = sandbox / "simv"

    def _run(self, cmd: List[str], cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
        # Prepend iverilog bin to path for child process
        print(f"[DEBUG] Running: {' '.join(cmd)}")
        env = os.environ.copy()
        if "C:\\iverilog\\bin" not in env.get("PATH", ""):
            env["PATH"] = "C:\\iverilog\\bin;" + env.get("PATH", "")
        proc = subprocess.run(cmd, env=env, cwd=str(cwd or self.sandbox), capture_output=True, text=True)
        if proc.returncode != 0:
            print(f"[DEBUG] Command failed with returncode {proc.returncode}")
            print(f"[DEBUG] STDOUT: {proc.stdout}")
            print(f"[DEBUG] STDERR: {proc.stderr}")
        return proc

    def lint_quick(self, dut_override: Optional[Path] = None, tb_override: Optional[Path] = None) -> Tuple[bool, str]:
        dut = dut_override or self.dut_path
        tb = tb_override or self.tb_path
        cmd = [VERILATOR_BIN, "--lint-only", str(dut), str(tb)]
        proc = self._run(cmd)
        text = proc.stdout + "\n" + proc.stderr
        write_text(self.verilator_log, text)
        return proc.returncode == 0, text

    def syntax_check(self, dut_override: Optional[Path] = None, tb_override: Optional[Path] = None) -> Tuple[bool, str]:
        dut = dut_override or self.dut_path
        tb = tb_override or self.tb_path
        cmd = [
            IVERILOG_BIN,
            "-g2012",
            "-y", r"d:\projects\ft816float\final_runnable_v\final_runnable_v\source",
            "-I", r"d:\projects\ft816float\final_runnable_v\final_runnable_v\source",
            str(dut),
            str(tb),
        ]
        proc = self._run(cmd)
        return proc.returncode == 0, proc.stdout + "\n" + proc.stderr

    def simulate(self, dut_override: Optional[Path] = None, tb_override: Optional[Path] = None,
                 stop_after_cycle: Optional[int] = None, tb_mode: int = 0, extra_defines: Optional[List[str]] = None,
                 sim_log_name: str = "sim.log") -> Tuple[bool, str, Path]:
        dut = dut_override or self.dut_path
        tb = tb_override or self.tb_path
        simv = self.sandbox / f"simv_mode{tb_mode}_{Path(sim_log_name).stem}.vvp"
        sim_log = self.sandbox / sim_log_name
        build_cmd = [
            IVERILOG_BIN,
            "-g2012",
            "-y", r"d:\projects\ft816float\final_runnable_v\final_runnable_v\source",
            "-I", r"d:\projects\ft816float\final_runnable_v\final_runnable_v\source",
            f"-DTB_MODE={tb_mode}",
            "-o",
            str(simv),
            str(dut),
            str(tb),
        ]
        if stop_after_cycle is not None:
            build_cmd.insert(-2, f"-DSTOP_AFTER_CYCLE={stop_after_cycle}")
        for d in extra_defines or []:
            # extra_defines usually look like "+define+VAR=VAL" or "+define+VAR"
            # convert to iverilog -DVAR=VAL
            clean_d = d.replace("+define+", "-D")
            build_cmd.insert(-2, clean_d)
        
        build = self._run(build_cmd)
        if build.returncode != 0:
            return False, build.stdout + "\n" + build.stderr, sim_log
        
        run = self._run([VVP_BIN, str(simv)])
        write_text(sim_log, run.stdout + "\n" + run.stderr)
        return run.returncode == 0, run.stdout + "\n" + run.stderr, sim_log

    @staticmethod
    def passed(log_path: Path) -> bool:
        if not log_path.exists():
            return False
        content = read_text(log_path)
        return "[TB] FINISH" in content and "[TB] [ERROR]" not in content


class TestbenchManager:
    def __init__(self, dut_file: Path):
        self.dut_file = dut_file
        self.metadata = VerilogParser.parse_interface(dut_file)

    def benchmark_family(self) -> str:
        name = self.dut_file.as_posix().lower()
        if "decoder_3_to_8" in name:
            return "decoder_3_to_8"
        if "first_counter_overflow" in name or "first_counter" in name:
            return "first_counter_overflow"
        if "flip_flop" in name or "tff" in name:
            return "tff"
        if "fsm_full" in name:
            return "fsm_full"
        if "lshift" in name:
            return "lshift_reg"
        if "mux_4_1" in name:
            return "mux_4_1"
        return "generic"

    def _signal_declarations(self) -> str:
        lines = []
        skip = {"clk", "clock", "rst", "rst_n", "reset", "reset_n"}
        for p in self.metadata.inputs:
            if p.name in skip:
                continue
            lines.append(f"reg{p.decl_width} {p.name};")
        for p in self.metadata.outputs:
            lines.append(f"wire{p.decl_width} {p.name};")
            lines.append(f"reg{p.decl_width} ref_{p.name};")
        return "\n".join(lines)

    def _dut_instantiation(self) -> str:
        joined = ",\n".join(f"    .{p.name}({p.name})" for p in self.metadata.ports)
        return f"{self.metadata.module_name} dut (\n{joined}\n  );"

    def _task_declarations(self) -> str:
        return "integer local_error_counter;\ninitial local_error_counter = 0;"

    def _snapshot_task(self) -> str:
        in_parts = []
        out_parts = []
        for p in self.metadata.inputs:
            if p.name.lower() not in {"clk", "clock", "rst", "rst_n", "reset", "reset_n"}:
                in_parts.append(f'"{p.name}=%b", {p.name}')
        for p in self.metadata.outputs:
            out_parts.append(f'"{p.name}=%b", {p.name}')
        fmt = ["[TB] [SNAPSHOT] CYCLE=%0d TESTCASE=%0d"]
        args = ["cycle_counter", "testcase_id"]
        if in_parts:
            fmt.extend([part.split(",", 1)[0].strip('"') for part in in_parts])
            args.extend([part.split(",", 1)[1].strip() for part in in_parts])
        if out_parts:
            fmt.extend([part.split(",", 1)[0].strip('"') for part in out_parts])
            args.extend([part.split(",", 1)[1].strip() for part in out_parts])
        fmt_str = " ".join(fmt)
        arg_str = ", ".join(args)
        return f'''task automatic emit_snapshot;\n  begin\n    $display("{fmt_str}", {arg_str});\n  end\nendtask'''

    def _builtin_sections(self, mode: str = "full") -> Optional[Dict[str, str]]:
        family = self.benchmark_family()
        ins = [p.name for p in self.metadata.inputs if p.name not in {"clk", "clock", "rst", "rst_n", "reset", "reset_n"}]
        outs = [p.name for p in self.metadata.outputs]
        clk_name = self.metadata.clock_names[0] if self.metadata.clock_names else "clk"
        rst_name = self.metadata.reset_names[0] if self.metadata.reset_names else "rst_n"
        random_sweeps = 24 if mode == "module" else 8

        if family == "decoder_3_to_8" and ins and outs:
            sel, y = ins[0], outs[0]
            base_stim = (
                f"for (i = 0; i < 8; i = i + 1) begin\n"
                f"  testcase_id = i;\n"
                f"  {sel} = i[2:0];\n"
                f"  #1;\n"
                f"end\n"
            )
            extra = ""
            if mode == "module":
                extra = (
                    f"for (i = 0; i < {random_sweeps}; i = i + 1) begin\n"
                    f"  testcase_id = 100 + i;\n"
                    f"  {sel} = $random;\n"
                    f"  #1;\n"
                    f"end\n"
                )
            return {
                "REFERENCE_MODEL_DECLARATIONS": "integer i;",
                "MONITOR_DECLARATIONS": "",
                "CHECKER_LOGIC": (
                    f"always @(*) begin\n"
                    f"  ref_{y} = 8'b0000_0000;\n"
                    f"  case ({sel})\n"
                    f"    3'd0: ref_{y} = 8'b0000_0001;\n"
                    f"    3'd1: ref_{y} = 8'b0000_0010;\n"
                    f"    3'd2: ref_{y} = 8'b0000_0100;\n"
                    f"    3'd3: ref_{y} = 8'b0000_1000;\n"
                    f"    3'd4: ref_{y} = 8'b0001_0000;\n"
                    f"    3'd5: ref_{y} = 8'b0010_0000;\n"
                    f"    3'd6: ref_{y} = 8'b0100_0000;\n"
                    f"    3'd7: ref_{y} = 8'b1000_0000;\n"
                    f"  endcase\n"
                    f"  if ({y} !== ref_{y}) begin\n"
                    f"    failure_count = failure_count + 1;\n"
                    f"    $display(\"[TB] [ERROR] TIME=%0d ASSERT=decoder_check SIGNAL={y} TESTCASE=%0d INPUT={sel}=%0d EXPECTED=%b ACTUAL=%b\", $time, testcase_id, {sel}, ref_{y}, {y});\n"
                    f"  end\n"
                    f"end"
                ),
                "STIMULUS_LOGIC": base_stim + extra,
            }

        if family == "first_counter_overflow" and outs:
            counter = next((o for o in outs if "count" in o.lower()), outs[0])
            overflow = next((o for o in outs if "overflow" in o.lower()), outs[-1])
            enable = next((i for i in ins if i.lower() in {"en", "enable"}), ins[0] if ins else None)
            base = (
                f"testcase_id = 0; {enable} = 0; repeat (2) @(posedge {clk_name});\n"
                f"testcase_id = 1; {enable} = 1; repeat (15) @(posedge {clk_name});\n"
                f"testcase_id = 2; {enable} = 0; repeat (2) @(posedge {clk_name});\n"
                f"testcase_id = 3; {enable} = 1; repeat (12) @(posedge {clk_name});\n"
            )
            extra = ""
            if mode == "module":
                extra = (
                    f"repeat ({random_sweeps}) begin\n"
                    f"  testcase_id = testcase_id + 1;\n"
                    f"  {enable} = $random;\n"
                    f"  @(posedge {clk_name});\n"
                    f"end\n"
                )
            return {
                "REFERENCE_MODEL_DECLARATIONS": f"reg [31:0] ref_cnt;\ninitial ref_cnt = 0;",
                "MONITOR_DECLARATIONS": "",
                "CHECKER_LOGIC": (
                    f"always @(posedge {clk_name} or negedge {rst_name}) begin\n"
                    f"  if (!{rst_name}) begin\n"
                    f"    ref_cnt <= 0;\n"
                    f"    ref_{counter} <= 0;\n"
                    f"    ref_{overflow} <= 0;\n"
                    f"  end else begin\n"
                    f"    if ({enable}) begin\n"
                    f"      if (ref_cnt == 9) begin\n"
                    f"        ref_cnt <= 0;\n"
                    f"        ref_{counter} <= 0;\n"
                    f"        ref_{overflow} <= 1;\n"
                    f"      end else begin\n"
                    f"        ref_cnt <= ref_cnt + 1;\n"
                    f"        ref_{counter} <= ref_cnt + 1;\n"
                    f"        ref_{overflow} <= 0;\n"
                    f"      end\n"
                    f"    end else begin\n"
                    f"      ref_{counter} <= ref_cnt;\n"
                    f"      ref_{overflow} <= 0;\n"
                    f"    end\n"
                    f"  end\n"
                    f"end\n"
                    f"always @(*) begin\n"
                    f"  if ({counter} !== ref_{counter}) begin\n"
                    f"    failure_count = failure_count + 1;\n"
                    f"    $display(\"[TB] [ERROR] TIME=%0d ASSERT=counter_check SIGNAL={counter} TESTCASE=%0d INPUT=en=%0b EXPECTED=%0d ACTUAL=%0d\", $time, testcase_id, {enable}, ref_{counter}, {counter});\n"
                    f"  end\n"
                    f"  if ({overflow} !== ref_{overflow}) begin\n"
                    f"    failure_count = failure_count + 1;\n"
                    f"    $display(\"[TB] [ERROR] TIME=%0d ASSERT=overflow_check SIGNAL={overflow} TESTCASE=%0d INPUT=en=%0b EXPECTED=%0b ACTUAL=%0b\", $time, testcase_id, {enable}, ref_{overflow}, {overflow});\n"
                    f"  end\n"
                    f"end"
                ),
                "STIMULUS_LOGIC": base + extra,
            }

        if family == "tff" and outs and ins:
            q = next((o for o in outs if o.lower() in {"q", "out"}), outs[0])
            t = next((i for i in ins if i.lower() in {"t", "toggle", "in"}), ins[0])
            base = (
                f"testcase_id = 0; {t} = 0; repeat (2) @(posedge {clk_name});\n"
                f"testcase_id = 1; {t} = 1; repeat (4) @(posedge {clk_name});\n"
                f"testcase_id = 2; {t} = 0; repeat (2) @(posedge {clk_name});\n"
                f"testcase_id = 3; {t} = 1; repeat (3) @(posedge {clk_name});\n"
            )
            extra = ""
            if mode == "module":
                extra = (
                    f"repeat ({random_sweeps}) begin\n"
                    f"  testcase_id = testcase_id + 1;\n"
                    f"  {t} = $random;\n"
                    f"  @(posedge {clk_name});\n"
                    f"end\n"
                )
            return {
                "REFERENCE_MODEL_DECLARATIONS": "",
                "MONITOR_DECLARATIONS": "",
                "CHECKER_LOGIC": (
                    f"always @(posedge {clk_name} or negedge {rst_name}) begin\n"
                    f"  if (!{rst_name}) ref_{q} <= 1'b0;\n"
                    f"  else if ({t}) ref_{q} <= ~ref_{q};\n"
                    f"end\n"
                    f"always @(*) begin\n"
                    f"  if ({q} !== ref_{q}) begin\n"
                    f"    failure_count = failure_count + 1;\n"
                    f"    $display(\"[TB] [ERROR] TIME=%0d ASSERT=tff_check SIGNAL={q} TESTCASE=%0d INPUT={t}=%b EXPECTED=%b ACTUAL=%b\", $time, testcase_id, {t}, ref_{q}, {q});\n"
                    f"  end\n"
                    f"end"
                ),
                "STIMULUS_LOGIC": base + extra,
            }

        return None

    def _llm_fill(self, dut_code: str, mode: str) -> Optional[Dict[str, str]]:
        prompt = f'''
Fill ONLY the parameterized slots of a fixed Verilog testbench template.
Return ONLY valid JSON with the keys:
- REFERENCE_MODEL_DECLARATIONS
- MONITOR_DECLARATIONS
- CHECKER_LOGIC
- STIMULUS_LOGIC

Constraints:
1. Do not rewrite the template skeleton.
2. The checker MUST print exactly this stable format:
   [TB] [ERROR] TIME=<time> ASSERT=<assertion> SIGNAL=<name> TESTCASE=<id> INPUT=<desc> EXPECTED=<value> ACTUAL=<value>
3. Use only IEEE-standard Verilog.
4. The reference model must reflect intended functionality, not the buggy logic.
5. For mode=module, add broader but still module-local stress stimuli.
6. Keep it concise.

MODE: {mode}
DUT CODE:
{dut_code}
'''
        res = LLMClient.call(prompt, self.dut_file.name, f"TB_FILL_{mode.upper()}", expect_json=True)
        need = {"REFERENCE_MODEL_DECLARATIONS", "MONITOR_DECLARATIONS", "CHECKER_LOGIC", "STIMULUS_LOGIC"}
        if not res or not need.issubset(set(res.keys())):
            return None
        return {k: clean_generated_verilog(str(res[k])) for k in need}

    def construct_tb(self, sandbox: Path, mode: str = "full") -> Optional[Path]:
        dut_code = read_text(self.dut_file)
        sections = self._builtin_sections(mode=mode) or self._llm_fill(dut_code, mode)
        if sections is None:
            return None
        tb = TB_TEMPLATE
        replace_map = {
            "// ${SIGNAL_DECLARATIONS}": self._signal_declarations(),
            "// ${REFERENCE_MODEL_DECLARATIONS}": sections.get("REFERENCE_MODEL_DECLARATIONS", ""),
            "// ${DUT_INSTANTIATION}": self._dut_instantiation(),
            "// ${MONITOR_DECLARATIONS}": sections.get("MONITOR_DECLARATIONS", ""),
            "// ${CHECKER_LOGIC}": sections.get("CHECKER_LOGIC", ""),
            "// ${TASK_DECLARATIONS}": self._task_declarations(),
            "// ${SNAPSHOT_TASK}": self._snapshot_task(),
            "// ${STIMULUS_LOGIC}": sections.get("STIMULUS_LOGIC", ""),
        }
        for k, v in replace_map.items():
            tb = tb.replace(k, v)
        tb_path = sandbox / f"tb_{mode}.sv"
        write_text(tb_path, tb)
        validator = Validator(sandbox, self.dut_file, tb_path)
        ok1, _ = validator.syntax_check(tb_override=tb_path)
        if not ok1:
            return None
        ok2, _, _ = validator.simulate(tb_override=tb_path, stop_after_cycle=8, tb_mode=0, sim_log_name=f"smoke_{mode}.log")
        if not ok2:
            return None
        return tb_path


class FaultAnalyzer:
    ERROR_RE = re.compile(
        r"\[TB\]\s+\[ERROR\]\s+TIME=(?P<time>\d+)\s+ASSERT=(?P<assertion>[^\s]+)\s+SIGNAL=(?P<signal>[^\s]+)\s+TESTCASE=(?P<testcase>-?\d+)\s+INPUT=(?P<input>.*?)\s+EXPECTED=(?P<expected>[^\s]+)\s+ACTUAL=(?P<actual>[^\s]+)",
        re.IGNORECASE,
    )
    TIMEOUT_RE = re.compile(r"\[TB\]\s+\[ERROR\]\s+TIME=(?P<time>\d+)\s+TYPE=SIM_TIMEOUT", re.IGNORECASE)
    SNAPSHOT_RE = re.compile(r"\[TB\]\s+\[SNAPSHOT\]\s+CYCLE=(?P<cycle>\d+)\s+TESTCASE=(?P<testcase>-?\d+)\s+(?P<body>.*)$")

    def parse_all_failures(self, sim_log_path: Path, family: str = "generic") -> List[FaultRecord]:
        faults = []
        if not sim_log_path.exists():
            return faults
        for line in read_text(sim_log_path).splitlines():
            m = self.ERROR_RE.search(line)
            if m:
                faults.append(FaultRecord(
                    t_err=int(m.group("time")),
                    input_repr=m.group("input"),
                    expected_repr=m.group("expected"),
                    actual_repr=m.group("actual"),
                    signal=m.group("signal"),
                    assertion=m.group("assertion"),
                    raw_line=line,
                    family=family,
                    testcase_id=int(m.group("testcase")),
                ))
                continue
            t = self.TIMEOUT_RE.search(line)
            if t:
                faults.append(FaultRecord(t_err=int(t.group("time")), signal="TIMEOUT", assertion="SIM_TIMEOUT", raw_line=line, family=family))
        return faults

    def parse_first_failure(self, sim_log_path: Path, family: str = "generic") -> FaultRecord:
        fs = self.parse_all_failures(sim_log_path, family=family)
        return fs[0] if fs else FaultRecord(family=family)

    def parse_snapshots(self, sim_log_path: Path, metadata: ModuleMetadata) -> List[TraceSnapshot]:
        out: List[TraceSnapshot] = []
        if not sim_log_path.exists():
            return out
        output_names = {p.name for p in metadata.outputs}
        input_names = {p.name for p in metadata.inputs}
        for line in read_text(sim_log_path).splitlines():
            m = self.SNAPSHOT_RE.search(line)
            if not m:
                continue
            body = m.group("body")
            inputs: Dict[str, str] = {}
            outputs: Dict[str, str] = {}
            for token in body.split():
                if "=" not in token:
                    continue
                k, v = token.split("=", 1)
                if k in output_names:
                    outputs[k] = v
                elif k in input_names:
                    inputs[k] = v
            out.append(TraceSnapshot(
                cycle=int(m.group("cycle")),
                testcase_id=int(m.group("testcase")),
                inputs=inputs,
                outputs=outputs,
                raw_line=line,
            ))
        return out

    def adaptive_window_k(self, family: str) -> int:
        if family in {"decoder_3_to_8", "mux_4_1"}:
            return 1
        if family in {"first_counter_overflow", "tff", "lshift_reg"}:
            return 2
        if family in {"fsm_full"}:
            return 4
        return 2

    def apply_window(self, fault: FaultRecord) -> FaultRecord:
        k = self.adaptive_window_k(fault.family)
        fault.window_k = k
        fault.window_start = max(0, fault.t_err - k)
        fault.window_end = fault.t_err + k
        return fault

    def binary_search_terr(self, validator: Validator, family: str, tb_path: Path, max_cycle: int = 128) -> int:
        low, high = 1, max_cycle
        ans = 0
        while low <= high:
            mid = (low + high) // 2
            _, _, log_path = validator.simulate(tb_override=tb_path, stop_after_cycle=mid, tb_mode=0, sim_log_name=f"terr_{mid}.log")
            fault = self.parse_first_failure(log_path, family=family)
            if fault.t_err > 0:
                ans = fault.t_err
                high = mid - 1
            else:
                low = mid + 1
        return ans

    def build_dependency_graph(self, code: str) -> Dict[str, List[str]]:
        graph: Dict[str, List[str]] = {}
        assign_re = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\b\s*(?:<=|=)\s*(.*?);")
        token_re = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
        for line in code.splitlines():
            m = assign_re.search(line)
            if not m:
                continue
            lhs = m.group(1)
            rhs = m.group(2)
            rhs_tokens = [t for t in token_re.findall(rhs) if t != lhs]
            graph.setdefault(lhs, []).extend(rhs_tokens)
        return graph

    def extract_signal_cone(self, code: str, target_signal: str, max_depth: int = 3) -> List[str]:
        graph = self.build_dependency_graph(code)
        visited = set()
        frontier = {target_signal}
        for _ in range(max_depth):
            nxt = set()
            for node in frontier:
                if node in visited:
                    continue
                visited.add(node)
                for dep in graph.get(node, []):
                    if dep not in visited:
                        nxt.add(dep)
            frontier = nxt
        visited.add(target_signal)
        return sorted(visited)

    @staticmethod
    def _hamming_like(a: Dict[str, str], b: Dict[str, str], keys: List[str]) -> int:
        score = 0
        for k in keys:
            if a.get(k) != b.get(k):
                score += 1
        return score

    def infer_twin_pair(self, fault: FaultRecord, snapshots: List[TraceSnapshot], cone: List[str]) -> TwinPair:
        if not snapshots:
            return TwinPair(
                failing_input=fault.input_repr,
                passing_input="N/A",
                expected_output=fault.expected_repr,
                actual_output=fault.actual_repr,
                hamming_distance=999,
                evidence=fault.raw_line,
            )
        fail_snap = None
        for s in snapshots:
            if abs(s.cycle - fault.t_err) <= max(1, fault.window_k) and (fault.testcase_id < 0 or s.testcase_id == fault.testcase_id):
                fail_snap = s
                break
        if fail_snap is None:
            fail_snap = min(snapshots, key=lambda s: abs(s.cycle - fault.t_err))
        best = None
        best_score = 10 ** 9
        key_space = sorted(set(cone) | set(fail_snap.inputs.keys()) | set(fail_snap.outputs.keys()))
        for cand in snapshots:
            if cand.cycle == fail_snap.cycle and cand.testcase_id == fail_snap.testcase_id:
                continue
            score = self._hamming_like({**fail_snap.inputs, **fail_snap.outputs}, {**cand.inputs, **cand.outputs}, key_space)
            score += abs(cand.cycle - fail_snap.cycle)
            if fault.testcase_id >= 0 and cand.testcase_id == fault.testcase_id:
                score += 3
            if score < best_score:
                best = cand
                best_score = score
        if best is None:
            return TwinPair(
                failing_input=fault.input_repr,
                passing_input="N/A",
                expected_output=fault.expected_repr,
                actual_output=fault.actual_repr,
                hamming_distance=999,
                evidence=fault.raw_line,
            )
        return TwinPair(
            failing_input=json.dumps(fail_snap.inputs, ensure_ascii=False),
            passing_input=json.dumps(best.inputs, ensure_ascii=False),
            expected_output=fault.expected_repr,
            actual_output=fault.actual_repr,
            hamming_distance=best_score,
            evidence=best.raw_line,
            twin_cycle=best.cycle,
            twin_testcase_id=best.testcase_id,
        )

    def build_structured_evidence(self, fault: FaultRecord, twin: TwinPair, cone: List[str],
                                  snapshots: List[TraceSnapshot], feedback_history: List[FeedbackPackage]) -> StructuredFaultEvidence:
        local = [s for s in snapshots if fault.window_start <= s.cycle <= fault.window_end]
        divergents = []
        for s in local[:12]:
            divergents.append({
                "cycle": s.cycle,
                "testcase_id": s.testcase_id,
                "inputs": s.inputs,
                "outputs": s.outputs,
            })
        return StructuredFaultEvidence(
            failing_case={
                "input": fault.input_repr,
                "expected": fault.expected_repr,
                "actual": fault.actual_repr,
                "signal": fault.signal,
                "assertion": fault.assertion,
                "testcase_id": fault.testcase_id,
            },
            passing_twin={
                "input": twin.passing_input,
                "expected": twin.expected_output,
                "actual": twin.actual_output,
                "hamming_distance": twin.hamming_distance,
                "cycle": twin.twin_cycle,
                "testcase_id": twin.twin_testcase_id,
                "evidence": twin.evidence,
            },
            earliest_failure_cycle=fault.t_err,
            first_assertion=fault.assertion,
            failure_signals=[fault.signal] if fault.signal != "N/A" else [],
            local_window={"start": fault.window_start, "end": fault.window_end, "k": fault.window_k},
            local_signal_cone=cone,
            divergent_snapshots=divergents,
            feedback_context=[asdict(x) for x in feedback_history[-3:]],
        )


class MinimalChangeSolver:
    def __init__(self, code: str, evidence: StructuredFaultEvidence):
        self.code = code
        self.evidence = evidence

    def _candidate_edits(self) -> List[Dict[str, Any]]:
        signal_set = set(self.evidence.local_signal_cone) | set(self.evidence.failure_signals)
        lines = self.code.splitlines()
        res = []
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            if any(sig in line for sig in signal_set):
                res.append({"line_no": idx, "kind": "signal_local", "line": line})
            if "case" in stripped:
                res.append({"line_no": idx, "kind": "case_line", "line": line})
            if re.search(r"\bif\s*\(", stripped):
                res.append({"line_no": idx, "kind": "if_line", "line": line})
            if re.search(r"<=|=", stripped):
                res.append({"line_no": idx, "kind": "assign_line", "line": line})
        uniq = []
        seen = set()
        for r in res:
            k = (r["line_no"], r["kind"])
            if k not in seen:
                seen.add(k)
                uniq.append(r)
        return uniq[:60]

    def solve(self) -> List[Dict[str, Any]]:
        cands = self._candidate_edits()
        if not cands or Optimize is None:
            return []
        opt = Optimize()
        xs = [Bool(f"x_{i}") for i in range(len(cands))]
        opt.add(Sum([If(x, 1, 0) for x in xs]) >= 1)
        penalties = []
        for i, c in enumerate(cands):
            locality_penalty = 0 if c["kind"] == "signal_local" else 1
            penalties.append(If(xs[i], locality_penalty, 0))
        opt.minimize(Sum([If(x, 1, 0) for x in xs]) + Sum(penalties))
        if opt.check() != sat:
            return []
        model = opt.model()
        picked = []
        for i, c in enumerate(cands):
            try:
                if bool(model.eval(xs[i])):
                    picked.append(c)
            except Exception:
                pass
        return picked[:8]


class DiagnosisEngine:
    def generate(self, evidence: StructuredFaultEvidence, code: str) -> DiagnosisReport:
        prompt = f'''
Generate a structured diagnosis report for RTL repair.
Return ONLY valid JSON with fields:
- error_pattern
- confidence
- difference_analysis
- root_cause
- fix_action
- location
- candidate_locations
- signal_layers
- constraints
- evidence_refs
- recommended_action
- edit_scope

Use the structured fault evidence directly. Keep the proposed edits local to the fault space.

Structured fault evidence:
{json.dumps(asdict(evidence), ensure_ascii=False, indent=2)}

Code:
{code}
'''
        res = LLMClient.call(prompt, "diagnosis", "DIAGNOSIS", expect_json=True)
        if not res:
            return DiagnosisReport(
                error_pattern="unknown_logic_error",
                confidence=0.35,
                difference_analysis=f"Mismatch on {','.join(evidence.failure_signals) or 'unknown signal'} around cycle {evidence.earliest_failure_cycle}.",
                root_cause="Heuristic fallback diagnosis based on structured evidence.",
                fix_action="Restrict edits to the signal cone and prefer minimal conditional/constant/index fixes.",
                location=(evidence.failure_signals[0] if evidence.failure_signals else "unknown"),
                candidate_locations=[{"location": s, "score": 0.7} for s in evidence.local_signal_cone[:5]],
                signal_layers={"cone": evidence.local_signal_cone},
                constraints=["minimal_change", "fault_space_only", "synthesizable"],
                evidence_refs=[json.dumps(evidence.failing_case, ensure_ascii=False)],
                recommended_action="Edit only inside the local signal cone and preserve all unrelated behavior.",
                edit_scope=evidence.local_signal_cone[:8],
            )
        return DiagnosisReport(
            error_pattern=str(res.get("error_pattern", "unknown_logic_error")),
            confidence=float(res.get("confidence", 0.35)),
            difference_analysis=str(res.get("difference_analysis", "")),
            root_cause=str(res.get("root_cause", "")),
            fix_action=str(res.get("fix_action", "")),
            location=str(res.get("location", evidence.failure_signals[0] if evidence.failure_signals else "unknown")),
            candidate_locations=list(res.get("candidate_locations", [])),
            signal_layers=dict(res.get("signal_layers", {"cone": evidence.local_signal_cone})),
            constraints=list(res.get("constraints", ["minimal_change", "fault_space_only", "synthesizable"])),
            evidence_refs=list(res.get("evidence_refs", [json.dumps(evidence.failing_case, ensure_ascii=False)])),
            recommended_action=str(res.get("recommended_action", res.get("fix_action", ""))),
            edit_scope=list(res.get("edit_scope", evidence.local_signal_cone[:8])),
        )


class CounterfactualAnalyzer:
    def build_envelope(self, evidence: StructuredFaultEvidence, snapshots: List[TraceSnapshot], cone: List[str]) -> Dict[str, Any]:
        local = []
        w0, w1 = evidence.local_window.get("start", 0), evidence.local_window.get("end", 0)
        for s in snapshots:
            if w0 <= s.cycle <= w1:
                local.append({
                    "cycle": s.cycle,
                    "testcase_id": s.testcase_id,
                    "inputs": s.inputs,
                    "outputs": s.outputs,
                })
        prompt = f"""
You are Agent-Counterfactual for RTL repair.
Goal: build a bounded counterfactual envelope near the earliest divergence.
Return ONLY JSON with keys:
- earliest_divergence_hypothesis
- candidate_root_signals (list)
- anchor_candidates (list of {{cycle,testcase_id,reason}})
- likely_propagated_signals (list)
- prioritized_edit_scope (list)
- confidence

Evidence:
{json.dumps(asdict(evidence), ensure_ascii=False)}

Local snapshots:
{json.dumps(local[:80], ensure_ascii=False)}

Signal cone:
{json.dumps(cone[:40], ensure_ascii=False)}
"""
        res = LLMClient.call(prompt, "counterfactual", "COUNTERFACTUAL_ANALYSIS", expect_json=True, model_name=AGENT_MODEL_DIAGNOSIS)
        if not res:
            return {
                "earliest_divergence_hypothesis": f"divergence near cycle {evidence.earliest_failure_cycle}",
                "candidate_root_signals": evidence.failure_signals[:COUNTERFACTUAL_TOPK],
                "anchor_candidates": [{"cycle": evidence.earliest_failure_cycle, "testcase_id": evidence.failing_case.get("testcase_id", -1), "reason": "fallback_anchor"}],
                "likely_propagated_signals": [],
                "prioritized_edit_scope": evidence.local_signal_cone[:8],
                "confidence": 0.35,
            }
        return res


class ReAnchorPatchAgent:
    def generate(self, family: str, diagnosis: DiagnosisReport, evidence: StructuredFaultEvidence,
                 counterfactual: Dict[str, Any], code: str, num_candidates: int = 3) -> List[PatchCandidate]:
        prompt = f"""
You are Agent-Patch for ReAnchor-style RTL repair.
Return ONLY valid JSON: {{"candidates":[...]}} with exactly up to {num_candidates} candidates.
Each candidate must include:
- patch_id
- rationale
- full_code

Constraints:
1) Minimal local edits only.
2) Prioritize counterfactual.prioritized_edit_scope and diagnosis.edit_scope.
3) Keep synthesizable Verilog.
4) Avoid touching unrelated modules and unrelated always blocks.

Family: {family}
Diagnosis: {json.dumps(asdict(diagnosis), ensure_ascii=False)}
Evidence: {json.dumps(asdict(evidence), ensure_ascii=False)}
Counterfactual: {json.dumps(counterfactual, ensure_ascii=False)}

Original code:
{code}
"""
        res = LLMClient.call(prompt, "reanchor_patch", "REANCHOR_PATCH", expect_json=True, model_name=AGENT_MODEL_PATCH)
        out = []
        for item in res.get("candidates", [])[:num_candidates]:
            new_code = clean_generated_verilog(item.get("full_code", ""))
            if not new_code:
                continue
            out.append(PatchCandidate(
                source="reanchor_agent",
                patch_id=str(item.get("patch_id", f"reanchor_{len(out)+1}")),
                code=new_code,
                edit_distance=line_edit_distance(code, new_code),
                note=str(item.get("rationale", "")),
            ))
        return out


class ProgressJudgeAgent:
    def decide_commit(self, prev_surface: Optional[FailureSurfaceState], cur_surface: FailureSurfaceState,
                      candidate: PatchCandidate, evidence: StructuredFaultEvidence) -> Dict[str, Any]:
        prompt = f"""
You are Agent-Validator for ReAnchor progress-preserving validation.
Decide whether this candidate should be COMMIT or REJECT.
Return ONLY JSON with keys:
- decision (COMMIT/REJECT)
- reason
- progress_score (0~1)
- regression_risk (0~1)

Previous surface:
{json.dumps(asdict(prev_surface), ensure_ascii=False) if prev_surface else "null"}

Current surface:
{json.dumps(asdict(cur_surface), ensure_ascii=False)}

Candidate summary:
{json.dumps({'patch_id': candidate.patch_id, 'source': candidate.source, 'q_score': candidate.q_score, 'full_pass': candidate.full_pass, 'module_pass': candidate.module_pass, 'local_pass': candidate.local_pass}, ensure_ascii=False)}

Evidence:
{json.dumps(asdict(evidence), ensure_ascii=False)}
"""
        res = LLMClient.call(prompt, "progress_judge", "PROGRESS_JUDGE", expect_json=True, model_name=AGENT_MODEL_VALIDATOR)
        if not res:
            return {"decision": "COMMIT" if candidate.module_pass or candidate.local_pass else "REJECT",
                    "reason": "fallback_rule_based",
                    "progress_score": 0.55 if (candidate.module_pass or candidate.local_pass) else 0.20,
                    "regression_risk": 0.35}
        return res


class TemplateLibrary:
    def __init__(self):
        self.pattern_to_templates = {
            "identifier_typo": ["rename_identifier"],
            "condition_polarity": ["flip_condition_polarity", "flip_enable_guard", "flip_reset_guard"],
            "comparison_operator": ["eq_neq_swap", "lt_le_swap", "gt_ge_swap"],
            "constant_value": ["replace_numeric_literal", "replace_case_label"],
            "bit_index_error": ["replace_bit_index", "swap_slice_order"],
            "missing_default": ["insert_default_case"],
            "assignment_style": ["blocking_to_nonblocking", "nonblocking_to_blocking"],
            "state_transition": ["repair_next_state_assignment", "insert_missing_state_update"],
            "reset_coverage": ["add_reset_assignment", "extend_reset_branch"],
            "overflow_timing": ["shift_overflow_flag_timing", "reset_overflow_on_nonterminal"],
            "port_direction_or_mapping": ["swap_port_connection", "rename_port_connection"],
            "width_mapping": ["fix_bitwidth_mask", "fix_high_low_mapping"],
        }

    def all_templates(self) -> List[str]:
        out = []
        for v in self.pattern_to_templates.values():
            out.extend(v)
        return sorted(set(out))


class TemplateRepairEngine:
    def __init__(self):
        self.library = TemplateLibrary()

    @staticmethod
    def _replace_once(pattern: str, repl: str, text: str, flags: int = re.MULTILINE) -> Optional[str]:
        new_text, n = re.subn(pattern, repl, text, count=1, flags=flags)
        return new_text if n > 0 else None

    def score_templates(self, code: str, diagnosis: DiagnosisReport, evidence: StructuredFaultEvidence) -> List[Tuple[str, float]]:
        templates = self.library.pattern_to_templates.get(diagnosis.error_pattern, self.library.all_templates())
        scope = set(diagnosis.edit_scope) | set(evidence.local_signal_cone)
        loc_lines = [i for i, line in enumerate(code.splitlines(), 1) if diagnosis.location and diagnosis.location in line]
        scope_lines = [i for i, line in enumerate(code.splitlines(), 1) if any(sig in line for sig in scope)]
        scored = []
        for tpl in templates:
            pattern_match = 1.0 if any(tok in diagnosis.fix_action.lower() for tok in tpl.split("_")) else 0.5
            location_match = 1.0 if loc_lines else 0.4
            signal_match = 1.0 if scope_lines else 0.4
            confidence_gate = diagnosis.confidence
            total = 0.35 * pattern_match + 0.30 * location_match + 0.20 * signal_match + 0.15 * confidence_gate
            scored.append((tpl, total))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [x for x in scored if x[1] >= 0.70]

    def instantiate(self, template_id: str, code: str, diagnosis: DiagnosisReport, evidence: StructuredFaultEvidence) -> Optional[str]:
        loc = diagnosis.location or (evidence.failure_signals[0] if evidence.failure_signals else "")
        expected_nums = re.findall(r"\d+", evidence.failing_case.get("expected", ""))
        if template_id == "rename_identifier" and loc and loc != "N/A":
            return self._replace_once(r"\boat\b", loc, code)
        if template_id == "flip_condition_polarity":
            return self._replace_once(r"if\s*\(([^\)]+)\)", r"if (!(\1))", code)
        if template_id == "flip_enable_guard":
            return self._replace_once(r"if\s*\(\s*(en|enable)\s*\)", r"if (!\1)", code, flags=re.IGNORECASE)
        if template_id == "flip_reset_guard":
            return self._replace_once(r"if\s*\(\s*!\s*(rst|rst_n|reset|reset_n)\s*\)", r"if (\1)", code, flags=re.IGNORECASE)
        if template_id == "eq_neq_swap" and loc:
            patched = self._replace_once(rf"\b{re.escape(loc)}\b\s*==", f"{loc} !=", code)
            return patched or self._replace_once(rf"\b{re.escape(loc)}\b\s*!=" , f"{loc} ==", code)
        if template_id == "replace_numeric_literal" and expected_nums:
            return self._replace_once(r"\b\d+\b", expected_nums[0], code)
        if template_id == "replace_case_label":
            inp = re.findall(r"\d+", evidence.failing_case.get("input", ""))
            if inp:
                return self._replace_once(r"3'b[01xXzZ_]+\s*:", f"3'd{inp[-1]}:", code)
        if template_id == "replace_bit_index":
            return self._replace_once(r"\[(\d+)\]", r"[0]", code)
        if template_id == "swap_slice_order":
            return self._replace_once(r"\[(\d+)\s*:\s*(\d+)\]", r"[\2:\1]", code)
        if template_id == "insert_default_case" and "case" in code and "default:" not in code:
            idx = code.rfind("endcase")
            if idx != -1:
                return code[:idx] + "  default: ;\n" + code[idx:]
        if template_id == "blocking_to_nonblocking":
            return self._replace_once(r"=", "<=", code)
        if template_id == "nonblocking_to_blocking":
            return self._replace_once(r"<=", "=", code)
        if template_id == "repair_next_state_assignment":
            return self._replace_once(r"\bn_state\b", "next_state", code)
        if template_id == "insert_missing_state_update":
            return self._replace_once(r"endcase", "default: n_state = state;\nendcase", code)
        if template_id == "add_reset_assignment" and loc:
            return self._replace_once(r"if\s*\(!?\s*(rst|rst_n|reset|reset_n)\s*\)\s*begin", rf"if (!\1) begin\n    {loc} <= 0;", code, flags=re.IGNORECASE)
        if template_id == "extend_reset_branch":
            return self._replace_once(r"if\s*\(!?\s*(rst|rst_n|reset|reset_n)\s*\)\s*begin", r"if (!\1) begin\n    // extended reset coverage", code, flags=re.IGNORECASE)
        if template_id == "shift_overflow_flag_timing":
            return self._replace_once(r"overflow\s*<=\s*1'b1", "overflow <= (count == 9)", code, flags=re.IGNORECASE)
        if template_id == "reset_overflow_on_nonterminal":
            return self._replace_once(r"overflow\s*<=\s*1'b1", "overflow <= 1'b0", code, flags=re.IGNORECASE)
        if template_id == "swap_port_connection":
            return self._replace_once(r"\.(\w+)\((\w+)\)", r".\2(\1)", code)
        if template_id == "rename_port_connection" and loc:
            return self._replace_once(rf"\.(\w+)\({re.escape(loc)}\)", rf".{loc}(\1)", code)
        if template_id == "fix_bitwidth_mask":
            return self._replace_once(r"8'b([01_]+)", "8'b1111_1111", code)
        if template_id == "fix_high_low_mapping":
            return self._replace_once(r"8'b0000_0001", "8'b1000_0000", code)
        return None

    def generate_candidates(self, code: str, diagnosis: DiagnosisReport, evidence: StructuredFaultEvidence) -> List[PatchCandidate]:
        out = []
        for tpl, score in self.score_templates(code, diagnosis, evidence):
            patched = self.instantiate(tpl, code, diagnosis, evidence)
            if patched and patched != code:
                out.append(PatchCandidate(
                    source="template",
                    patch_id=tpl,
                    code=patched,
                    edit_distance=line_edit_distance(code, patched),
                    note=f"template_score={score:.2f}",
                ))
        return out


class RAGPatchGenerator:
    def __init__(self, kb: KnowledgeBase):
        self.kb = kb

    def generate(self, family: str, diagnosis: DiagnosisReport, evidence: StructuredFaultEvidence, code: str, num_candidates: int = 3) -> List[PatchCandidate]:
        refs = self.kb.retrieve(family, diagnosis, limit=5)
        prompt = f'''
You are generating constrained RTL repair candidates.
Return ONLY valid JSON with a top-level key candidates, whose value is a list of {num_candidates} objects.
Each candidate object must contain:
- patch_id
- rationale
- full_code

Constraints:
1. Generate local, minimal edits only.
2. Restrict changes to diagnosis.edit_scope and evidence.local_signal_cone when possible.
3. Must remain synthesizable Verilog.
4. Prefer readability and small edit distance.
5. Use feedback_context to avoid repeating rejected patch patterns.

Family: {family}
Diagnosis: {json.dumps(asdict(diagnosis), ensure_ascii=False, indent=2)}
Evidence: {json.dumps(asdict(evidence), ensure_ascii=False, indent=2)}
Retrieved examples: {json.dumps(refs, ensure_ascii=False, indent=2)}
Code:
{code}
'''
        res = LLMClient.call(prompt, "rag_patch", "RAG_PATCH", expect_json=True, model_name=MODEL_NAME)
        candidates = []
        for item in res.get("candidates", [])[:num_candidates]:
            full_code = clean_generated_verilog(item.get("full_code", ""))
            if full_code:
                candidates.append(PatchCandidate(
                    source="rag_fallback",
                    patch_id=str(item.get("patch_id", f"rag_{len(candidates)+1}")),
                    code=full_code,
                    edit_distance=line_edit_distance(code, full_code),
                    note=str(item.get("rationale", "")),
                ))
        return candidates


class SyntaxFixer:
    @staticmethod
    def fix_with_llm(dut_file: Path, compiler_text: str) -> bool:
        code = read_text(dut_file)
        prompt = f'''
Fix only syntax errors in this Verilog code.
Return ONLY the full corrected Verilog code.
Do not change behavior unless needed for syntax validity.

Compiler output:
{compiler_text}

Code:
{code}
'''
        res = LLMClient.call(prompt, dut_file.name, "SYNTAX_FIX", expect_json=False)
        if not res or "raw_content" not in res:
            return False
        new_code = clean_generated_verilog(res["raw_content"])
        if not new_code.strip():
            return False
        write_text(dut_file, new_code)
        return True


def score_readability(code: str) -> float:
    lines = [x for x in code.splitlines() if x.strip()]
    if not lines:
        return 0.0
    comment_bonus = 0.1 if any("//" in x for x in lines) else 0.0
    long_line_penalty = min(0.3, sum(1 for x in lines if len(x) > 120) / max(1, len(lines)))
    indent_ok = sum(1 for x in lines if x.startswith("    ") or not x.startswith(" ")) / len(lines)
    return max(0.0, min(1.0, 0.6 * indent_ok + 0.3 + comment_bonus - long_line_penalty))


def calculate_q_score(correctness: float, delta_size: int, synthesizable: bool, readable_score: float) -> Tuple[float, float, float, float, float]:
    scorr = max(0.0, min(1.0, correctness))
    smin = 1.0 / (1.0 + max(delta_size, 0))
    ssynth = 1.0 if synthesizable else 0.0
    sread = max(0.0, min(1.0, readable_score))
    q = 0.5 * scorr + 0.2 * smin + 0.2 * ssynth + 0.1 * sread
    return scorr, smin, ssynth, sread, q


class CandidateRanker:
    def __init__(self, module_tb: Path, full_tb: Path):
        self.module_tb = module_tb
        self.full_tb = full_tb

    def _package_feedback(self, round_id: int, cand: PatchCandidate, evidence: StructuredFaultEvidence,
                          failed_stage: str, failed_log: str, diagnosis: DiagnosisReport) -> FeedbackPackage:
        return FeedbackPackage(
            round_id=round_id,
            failed_stage=failed_stage,
            triggering_tests=[evidence.failing_case.get("testcase_id", -1)],
            first_failed_assertion=evidence.first_assertion,
            failure_cycle=evidence.earliest_failure_cycle,
            divergent_signals=evidence.failure_signals,
            failed_patch_id=cand.patch_id,
            diagnosis_summary=diagnosis.root_cause,
            validator_excerpt="\n".join(failed_log.splitlines()[:20]),
        )

    def validate_candidates(self, validator: Validator, original_code: str, candidates: List[PatchCandidate],
                            evidence: StructuredFaultEvidence, diagnosis: DiagnosisReport, round_id: int) -> Tuple[List[PatchCandidate], List[FeedbackPackage]]:
        ranked = []
        feedbacks: List[FeedbackPackage] = []
        candidate_dir = validator.sandbox / f"candidates_round_{round_id}"
        candidate_dir.mkdir(exist_ok=True)

        local_stop = max(8, evidence.local_window["end"] + 2)
        for idx, cand in enumerate(candidates, 1):
            dut_path = candidate_dir / f"cand_{idx}.v"
            write_text(dut_path, cand.code)

            lint_ok, lint_log = validator.lint_quick(dut_override=dut_path, tb_override=self.full_tb)
            cand.syntax_ok = lint_ok
            cand.stage_logs["stage1_lint"] = lint_log
            if not lint_ok:
                feedbacks.append(self._package_feedback(round_id, cand, evidence, "stage1_lint", lint_log, diagnosis))
                ranked.append(cand)
                continue

            static_ok, static_log = validator.syntax_check(dut_override=dut_path, tb_override=self.full_tb)
            cand.static_ok = static_ok
            cand.synth_ok = static_ok
            cand.stage_logs["stage1_static"] = static_log
            if not static_ok:
                feedbacks.append(self._package_feedback(round_id, cand, evidence, "stage1_static", static_log, diagnosis))
                ranked.append(cand)
                continue

            _, local_run_log, local_log_path = validator.simulate(dut_override=dut_path, tb_override=self.full_tb,
                                                                  stop_after_cycle=local_stop, tb_mode=0,
                                                                  sim_log_name=f"cand_{idx}_local.log")
            cand.local_pass = Validator.passed(local_log_path)
            cand.stage_logs["stage2_local"] = local_run_log
            if not cand.local_pass:
                feedbacks.append(self._package_feedback(round_id, cand, evidence, "stage2_local", local_run_log, diagnosis))
                ranked.append(cand)
                continue

            _, module_run_log, module_log_path = validator.simulate(dut_override=dut_path, tb_override=self.module_tb,
                                                                    tb_mode=1, sim_log_name=f"cand_{idx}_module.log")
            cand.module_pass = Validator.passed(module_log_path)
            cand.stage_logs["stage3_module"] = module_run_log
            if not cand.module_pass:
                feedbacks.append(self._package_feedback(round_id, cand, evidence, "stage3_module", module_run_log, diagnosis))
                ranked.append(cand)
                continue

            _, full_run_log, full_log_path = validator.simulate(dut_override=dut_path, tb_override=self.full_tb,
                                                                tb_mode=0, sim_log_name=f"cand_{idx}_full.log")
            cand.full_pass = Validator.passed(full_log_path)
            cand.stage_logs["stage4_full"] = full_run_log
            if not cand.full_pass:
                feedbacks.append(self._package_feedback(round_id, cand, evidence, "stage4_full", full_run_log, diagnosis))

            scorr, smin, ssynth, sread, q = calculate_q_score(
                correctness=1.0 if cand.full_pass else (0.66 if cand.module_pass else 0.33 if cand.local_pass else 0.0),
                delta_size=cand.edit_distance,
                synthesizable=cand.synth_ok,
                readable_score=score_readability(cand.code),
            )
            cand.correctness_score = scorr
            cand.minimality_score = smin
            cand.synthesizability_score = ssynth
            cand.readability_score = sread
            cand.q_score = q
            ranked.append(cand)

        ranked.sort(key=lambda c: (c.full_pass, c.q_score, -c.edit_distance), reverse=True)
        return ranked, feedbacks


class RepairStats:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.results: List[Dict[str, Any]] = []
        self.start_time = time.time()

    def add_record(self, filename: str, success_round: int, duration: float, q_score: float, note: str = "", loc: int = 0) -> None:
        self.results.append({
            "file": filename,
            "success_round": success_round,
            "duration": duration,
            "q_score": q_score,
            "note": note,
            "loc": loc,
        })

    def generate_report(self) -> None:
        total = len(self.results)
        if total == 0:
            return
        s1 = sum(1 for r in self.results if 0 < r["success_round"] <= 1)
        s3 = sum(1 for r in self.results if 0 < r["success_round"] <= 3)
        s5 = sum(1 for r in self.results if 0 < r["success_round"] <= 5)
        avg_time = sum(r["duration"] for r in self.results) / total
        avg_loc = sum(r["loc"] for r in self.results) / total
        report = [
            "============================================================",
            "FINAL EXPERIMENT REPORT (STRICT PAPER-ALIGNED)",
            "============================================================",
            f"Total Files: {total}",
            f"Success Rate (1 Round): {s1}/{total} ({s1/total*100:.1f}%)",
            f"Success Rate (3 Rounds): {s3}/{total} ({s3/total*100:.1f}%)",
            f"Success Rate (5 Rounds): {s5}/{total} ({s5/total*100:.1f}%)",
            f"Average Repair Time: {avg_time:.2f}s",
            f"Average Patch LOC: {avg_loc:.2f}",
            f"Total Experiment Duration: {time.time() - self.start_time:.2f}s",
            "",
            "Details:",
        ]
        for r in self.results:
            status = f"Passed at Round {r['success_round']}" if r["success_round"] > 0 else "FAILED"
            report.append(f"- {r['file']}: {status} | Time: {r['duration']:.1f}s | Q: {r['q_score']:.2f} | LOC: {r['loc']} | {r['note']}")
        write_text(self.output_dir / "experiment_report.txt", "\n".join(report) + "\n")
        print("\n".join(report))


class RepairPipeline:
    def __init__(self):
        self.kb = KnowledgeBase(KNOWLEDGE_DIR)
        self.template_engine = TemplateRepairEngine()
        self.diag_engine = DiagnosisEngine()
        self.rag_engine = RAGPatchGenerator(self.kb)
        self.counterfactual_agent = CounterfactualAnalyzer()
        self.reanchor_patch_agent = ReAnchorPatchAgent()
        self.progress_judge_agent = ProgressJudgeAgent()

    def family_of(self, dut_path: Path) -> str:
        return TestbenchManager(dut_path).benchmark_family()

    def build_candidates(self, original_code: str, diagnosis: DiagnosisReport,
                         evidence: StructuredFaultEvidence, counterfactual: Dict[str, Any],
                         family: str) -> List[PatchCandidate]:
        out = []
        out.extend(self.reanchor_patch_agent.generate(family, diagnosis, evidence, counterfactual, original_code, num_candidates=3))
        template_candidates = self.template_engine.generate_candidates(original_code, diagnosis, evidence)
        if diagnosis.confidence >= 0.60 and template_candidates:
            out.extend(template_candidates)
        else:
            out.extend(template_candidates[:2])
            out.extend(self.rag_engine.generate(family, diagnosis, evidence, original_code, num_candidates=2))
        unique: List[PatchCandidate] = []
        seen = set()
        for cand in out:
            key = sha1_text(cand.code)
            if key not in seen and cand.code != original_code:
                seen.add(key)
                unique.append(cand)
        return unique[:MAX_CANDIDATES_PER_ROUND]

    def run_repair_flow(self, dut_rel_path: str, stats: RepairStats, max_rounds: int = MAX_ROUNDS) -> None:
        dut_abs = (BASE_DIR / dut_rel_path).resolve()
        dut_name = dut_abs.name
        family = self.family_of(dut_abs)
        start_t = time.time()
        sandbox = stats.output_dir / f"work_{dut_abs.stem}"

        if RESUME_MODE and (sandbox / "sim.log").exists():
            sim_content = read_text(sandbox / "sim.log")
            if "[TB] FINISH" in sim_content and "[TB] [ERROR]" not in sim_content:
                return

        if sandbox.exists():
            shutil.rmtree(sandbox)
        sandbox.mkdir(parents=True, exist_ok=True)
        internal_dut = sandbox / dut_name
        shutil.copy2(dut_abs, internal_dut)

        tbm = TestbenchManager(internal_dut)
        full_tb = tbm.construct_tb(sandbox, mode="full")
        module_tb = tbm.construct_tb(sandbox, mode="module")
        if full_tb is None or module_tb is None:
            stats.add_record(dut_name, 0, time.time() - start_t, 0.0, note="TB generation failed", loc=0)
            return

        ranker = CandidateRanker(module_tb=module_tb, full_tb=full_tb)
        feedback_history: List[FeedbackPackage] = []
        success_round = 0
        final_q = 0.0
        final_note = ""
        final_loc = 0

        prev_surface: Optional[FailureSurfaceState] = None

        for round_id in range(1, max_rounds + 1):
            validator = Validator(sandbox, internal_dut, full_tb)
            lint_ok, lint_msg = validator.lint_quick(tb_override=full_tb)
            syntax_ok, analyze_msg = validator.syntax_check(tb_override=full_tb)
            if not syntax_ok:
                if not SyntaxFixer.fix_with_llm(internal_dut, analyze_msg or lint_msg):
                    final_note = f"Syntax fix failed at round {round_id}"
                    continue

            _, _, full_log = validator.simulate(tb_override=full_tb, tb_mode=0, sim_log_name=f"round_{round_id}_full_pre.log")
            if Validator.passed(full_log):
                success_round = round_id
                final_loc = line_edit_distance(read_text(dut_abs), read_text(internal_dut))
                _, _, _, _, final_q = calculate_q_score(1.0, final_loc, True, score_readability(read_text(internal_dut)))
                final_note = "Full regression passed"
                break

            fa = FaultAnalyzer()
            terr = fa.binary_search_terr(validator, family=family, tb_path=full_tb, max_cycle=128)
            fault = fa.parse_first_failure(full_log, family=family)
            if terr > 0:
                fault.t_err = terr
            fault = fa.apply_window(fault)
            if fault.t_err == 0:
                final_note = f"No machine-readable failure at round {round_id}"
                continue

            code = read_text(internal_dut)
            local_error_count = full_log.count("[TB] [ERROR]")
            current_surface = FailureSurfaceState(
                round_id=round_id,
                earliest_failure_cycle=fault.t_err,
                failing_assertion=fault.assertion,
                failing_signal=fault.signal,
                local_window_k=fault.window_k,
                local_error_count=local_error_count,
                note="pre-patch",
            )
            snapshots = fa.parse_snapshots(full_log, tbm.metadata)
            cone = fa.extract_signal_cone(code, fault.signal, max_depth=3)
            twin = fa.infer_twin_pair(fault, snapshots, cone)
            evidence = fa.build_structured_evidence(fault, twin, cone, snapshots, feedback_history)
            counterfactual = self.counterfactual_agent.build_envelope(evidence, snapshots, cone)
            diagnosis = self.diag_engine.generate(evidence, code)

            prioritized_scope = list(counterfactual.get("prioritized_edit_scope", []))
            if prioritized_scope:
                diagnosis.edit_scope = list(dict.fromkeys(prioritized_scope + diagnosis.edit_scope))

            solver = MinimalChangeSolver(code, evidence)
            smt_hints = solver.solve()
            if smt_hints:
                diagnosis.constraints.append(f"smt_selected_lines={[h['line_no'] for h in smt_hints]}")
                diagnosis.edit_scope.extend(sorted({str(h['line_no']) for h in smt_hints}))

            candidates = self.build_candidates(code, diagnosis, evidence, counterfactual, family)
            if not candidates:
                final_note = f"No patch candidates at round {round_id}"
                continue

            ranked, feedbacks = ranker.validate_candidates(validator, code, candidates, evidence, diagnosis, round_id)
            feedback_history.extend(feedbacks)
            best = ranked[0]
            post_surface = FailureSurfaceState(
                round_id=round_id,
                earliest_failure_cycle=evidence.earliest_failure_cycle,
                failing_assertion=evidence.first_assertion,
                failing_signal=(evidence.failure_signals[0] if evidence.failure_signals else "N/A"),
                local_window_k=evidence.local_window.get("k", 0),
                local_error_count=0 if best.full_pass else max(0, current_surface.local_error_count - (1 if best.local_pass else 0)),
                regressions=0 if best.local_pass else 1,
                simplification_score=max(0.0, best.correctness_score - REANCHOR_PROGRESS_MARGIN),
                note="post-patch-estimated",
            )
            decision = self.progress_judge_agent.decide_commit(prev_surface, post_surface, best, evidence)
            do_commit = str(decision.get("decision", "REJECT")).upper() == "COMMIT"
            progress_score = float(decision.get("progress_score", 0.0))

            if best.full_pass:
                do_commit = True
                progress_score = max(progress_score, 1.0)

            if do_commit or best.module_pass or best.local_pass:
                write_text(internal_dut, best.code)
                final_note = f"Committed {best.source}:{best.patch_id} | progress={progress_score:.2f} | {decision.get('reason','')}"
                final_loc = line_edit_distance(code, best.code)
                prev_surface = post_surface
            else:
                final_note = f"Rejected {best.source}:{best.patch_id} | {decision.get('reason','')}"

            if best.full_pass:
                success_round = round_id
                final_q = best.q_score
                self.kb.add_case(family, diagnosis, best, evidence)
                break

        if success_round == 0:
            delta = line_edit_distance(read_text(dut_abs), read_text(internal_dut)) if internal_dut.exists() else 999
            _, _, _, _, final_q = calculate_q_score(0.0, delta, False, score_readability(read_text(internal_dut)) if internal_dut.exists() else 0.0)
            if final_loc == 0:
                final_loc = delta

        stats.add_record(dut_name, success_round, time.time() - start_t, final_q, note=final_note, loc=final_loc)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ReAnchor-style RTL repair pipeline")
    parser.add_argument("--dut", action="append", default=[], help="Relative DUT path under BASE_DIR. Can be provided multiple times.")
    parser.add_argument("--dut-list", default="", help="Text file containing DUT relative paths, one per line.")
    parser.add_argument("--max-rounds", type=int, default=MAX_ROUNDS, help="Max repair rounds per DUT.")
    args = parser.parse_args()

    targets: List[str] = []
    targets.extend([x.strip() for x in args.dut if x and x.strip()])
    if args.dut_list:
        dut_list_path = Path(args.dut_list)
        if not dut_list_path.is_absolute():
            dut_list_path = (BASE_DIR / dut_list_path).resolve()
        if dut_list_path.exists():
            for line in read_text(dut_list_path).splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    targets.append(line)

    targets = list(dict.fromkeys(targets))
    if not targets:
        print("No DUT targets provided. Use --dut <relative_path> or --dut-list <file>.")
        raise SystemExit(0)

    stats = RepairStats(EXPERIMENT_DIR)
    pipeline = RepairPipeline()

    for rel in targets:
        try:
            pipeline.run_repair_flow(rel, stats, max_rounds=args.max_rounds)
        except Exception as exc:
            stats.add_record(Path(rel).name, 0, 0.0, 0.0, note=f"Unhandled exception: {exc}", loc=0)

    stats.generate_report()

