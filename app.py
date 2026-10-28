import ast, random
import numpy as np
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="그래프 슈터", page_icon="🎯", layout="wide")

X_MIN, X_MAX, Y_MIN, Y_MAX = -10, 10, -10, 10
SHOTS_PER_STAGE = 5

# ---------- 안전한 수식 파서 ----------
FUNCS = {"sin": np.sin, "cos": np.cos, "tan": np.tan, "exp": np.exp,
         "log": np.log, "sqrt": np.sqrt, "abs": np.abs, "pi": np.pi, "e": np.e}
ALLOWED = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Name, ast.Load,
           ast.Call, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.USub, ast.UAdd, ast.Mod)

def make_func(expr: str):
    expr = expr.replace("^", "**").replace("y=", "").replace("Y=", "").strip()
    tree = ast.parse(expr, mode="eval")
    for node in ast.walk(tree):
        if not isinstance(node, ALLOWED):
            raise ValueError("허용되지 않는 표현이 있어요.")
        if isinstance(node, ast.Name) and node.id != "x" and node.id not in FUNCS:
            raise ValueError(f"알 수 없는 이름: {node.id}")
    code = compile(tree, "<f>", "eval")
    return lambda x: eval(code, {"__builtins__": {}}, {**FUNCS, "x": x})

# ---------- 게임 상태 ----------
def new_stage(stage):
    rnd = random.Random()
    player = (X_MIN + 1, rnd.uniform(-6, 6))
    def free(x, y, r, objs):
        return all((x-o[0])**2 + (y-o[1])**2 > (r+o[2]+0.5)**2 for o in objs) and abs(x-player[0]) > 3
    targets, obstacles = [], []
    while len(targets) < min(2 + stage, 6):
        x, y = rnd.uniform(0, 9), rnd.uniform(-8, 8)
        if free(x, y, 0.6, targets): targets.append((x, y, 0.6))
    while len(obstacles) < min(1 + stage, 7):
        x, y, r = rnd.uniform(-6, 7), rnd.uniform(-8, 8), rnd.uniform(0.8, 1.8)
        if free(x, y, r, targets + obstacles): obstacles.append((x, y, r))
    st.session_state.update(player=player, targets=targets, obstacles=obstacles,
                            shots=SHOTS_PER_STAGE, last_path=None, msg="")

if "stage" not in st.session_state:
    st.session_state.update(stage=1, score=0, game_over=False)
    new_stage(1)

def fire(expr):
    f = make_func(expr)
    px, py = st.session_state.player
    xs = np.linspace(px, X_MAX, 800)
    with np.errstate(all="ignore"):
        ys = np.asarray(f(xs), dtype=float) * np.ones_like(xs)
        y0 = float(np.asarray(f(px), dtype=float))
    if not np.isfinite(y0):
        raise ValueError("발사 위치에서 함수값이 정의되지 않아요.")
    ys = ys - y0 + py                      # 그래프를 플레이어 위치로 평행이동
    path_x, path_y, hit = [], [], []
    targets = list(st.session_state.targets)
    end_reason = "화면 밖으로 나감"
    for x, y in zip(xs, ys):
        if not np.isfinite(y) or y < Y_MIN or y > Y_MAX:
            end_reason = "화면 밖으로 나감"; break
        path_x.append(x); path_y.append(y)
        if any((x-ox)**2 + (y-oy)**2 < r**2 for ox, oy, r in st.session_state.obstacles):
            end_reason = "장애물에 막힘 💥"; break
        for t in targets[:]:
            if (x-t[0])**2 + (y-t[1])**2 < t[2]**2:
                targets.remove(t); hit.append(t)
    st.session_state.targets = targets
    st.session_state.shots -= 1
    st.session_state.score += 100 * len(hit) * (2 if len(hit) > 1 else 1)
    st.session_state.last_path = (path_x, path_y)
    st.session_state.msg = f"명중 {len(hit)}개! ({end_reason})"
    if not targets:
        st.session_state.score += 50 * st.session_state.shots
        st.session_state.stage += 1
        st.balloons()
        new_stage(st.session_state.stage)
        st.session_state.msg = f"🎉 스테이지 클리어! 스테이지 {st.session_state.stage} 시작"
        st.session_state.last_path = (path_x, path_y)
    elif st.session_state.shots <= 0:
        st.session_state.game_over = True

# ---------- 그리기 ----------
def circle(x, y, r, color, name):
    t = np.linspace(0, 2*np.pi, 40)
    return go.Scatter(x=x + r*np.cos(t), y=y + r*np.sin(t), fill="toself", mode="lines",
                      line=dict(color=color), fillcolor=color, name=name,
                      showlegend=False, hoverinfo="skip")

def draw():
    fig = go.Figure()
    for o in st.session_state.obstacles: fig.add_trace(circle(*o, "rgba(120,120,120,0.8)", "장애물"))
    for t in st.session_state.targets: fig.add_trace(circle(*t, "rgba(230,60,60,0.9)", "타겟"))
    px, py = st.session_state.player
    fig.add_trace(go.Scatter(x=[px], y=[py], mode="markers+text", text=["🔫"], textposition="top center",
                             marker=dict(size=16, color="royalblue"), showlegend=False))
    frames = []
    if st.session_state.last_path:
        xs, ys = st.session_state.last_path
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color="orange", dash="dot"), showlegend=False))
        fig.add_trace(go.Scatter(x=xs[:1], y=ys[:1], mode="markers",
                                 marker=dict(size=12, color="gold", line=dict(color="black", width=1)), showlegend=False))
        bi = len(fig.data) - 1
        step = max(1, len(xs)//60)
        frames = [go.Frame(data=[go.Scatter(x=[xs[i]], y=[ys[i]])], traces=[bi])
                  for i in range(0, len(xs), step)] + [go.Frame(data=[go.Scatter(x=[xs[-1]], y=[ys[-1]])], traces=[bi])]
        fig.frames = frames
        fig.update_layout(updatemenus=[dict(type="buttons", x=0, y=1.08, showactive=False,
            buttons=[dict(label="▶ 총알 재생", method="animate",
                          args=[None, dict(frame=dict(duration=25, redraw=False), fromcurrent=False)])])])
    fig.update_layout(xaxis=dict(range=[X_MIN, X_MAX], zeroline=True, dtick=2),
                      yaxis=dict(range=[Y_MIN, Y_MAX], zeroline=True, dtick=2, scaleanchor="x"),
                      height=640, margin=dict(l=10, r=10, t=40, b=10), plot_bgcolor="#f7f9fc")
    return fig

# ---------- UI ----------
st.title("🎯 그래프 슈터")
st.caption("함수식을 입력하면 총알이 그 그래프 궤도로 날아갑니다. 회색 장애물을 피해 빨간 타겟을 모두 맞히세요!")

left, right = st.columns([1, 2.4])
with left:
    c1, c2, c3 = st.columns(3)
    c1.metric("스테이지", st.session_state.stage)
    c2.metric("점수", st.session_state.score)
    c3.metric("남은 탄", st.session_state.shots)
    with st.form("shoot"):
        expr = st.text_input("y = ", value="0.1*x^2", help="예: 2*sin(x), x^3/50, -0.5*x, abs(x)-3")
        shot = st.form_submit_button("🔥 발사", use_container_width=True, disabled=st.session_state.game_over)
    if shot:
        try:
            fire(expr)
        except Exception as ex:
            st.error(f"수식 오류: {ex}")
    if st.session_state.msg: st.info(st.session_state.msg)
    if st.session_state.game_over:
        st.error(f"💀 게임 오버! 최종 점수 {st.session_state.score}")
    if st.button("🔄 새 게임", use_container_width=True):
        st.session_state.clear(); st.rerun()
    with st.expander("📘 규칙 & 사용 가능한 함수"):
        st.markdown("""
- 총알은 🔫 위치에서 출발해 **오른쪽으로** 진행합니다.
- 입력한 그래프는 **발사 위치를 지나도록 자동 평행이동**됩니다 (모양이 중요!).
- 한 발로 여러 타겟을 맞히면 **점수 2배**, 남은 탄은 클리어 보너스.
- 사용 가능: `+ - * / ^`, `sin cos tan exp log sqrt abs pi e`
""")
with right:
    st.plotly_chart(draw(), use_container_width=True)
