"""Edit actual UI screenshots into a 90-second captioned demonstration.

This is an interface walkthrough edited from captures, not a continuous recording.
Development dependency: imageio-ffmpeg==0.6.0. No browser automation occurs here.
"""
from pathlib import Path
import subprocess
import imageio_ffmpeg

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT.parents[1]/"work/video"
WORK.mkdir(parents=True,exist_ok=True)
scenes=[
 ("01-overview.jpg",6,"01 / 产业研究工作台：固态电池，六家公司、七条关系。\n历史证据样本；本机运行真实 FastAPI / LangGraph，默认规则模式。"),
 ("02-chain.jpg",6,"按产业环节、市场和技术路径查看关系。\n全固态、半固态、固态隔膜与凝聚态分别标识，缺失证据不代表零收入。"),
 ("03-revenue.jpg",15,"02 / 收入证据：约 1,180 万美元来自产线安装与技术转移。\n不是电芯量产收入；同一公司的电解质研发关系仍评 B。"),
 ("04-compare.jpg",14,"03 / 跨市场对照：解释为何可比，以及哪些部分不可比。\n赣锋半固态与 QS 固态隔膜平台不可混用，QS 年报原型正极仍含液态电解液。"),
 ("05-transmission.jpg",16,"04 / 外部情景沿环节传到业务与待验证财务指标。\n成立条件和反向机制同时保留；不把背景引用当作冲击已发生的证据。"),
 ("06-sensitivity.jpg",12,"05 / 敏感度：当假设降本全部转移给客户，保留贡献变为 0。\n参数都是用户假设，输出不是公司毛利率或盈利预测。"),
 ("07-evidence.jpg",11,"06 / 证据台账：材料定位、发布日期、摘要校验与原文链接。\n新材料先待审，人工复核后重新评级；保存快照并对照版本变化。"),
 ("08-boundary.jpg",10,"07 / 边界验证：目标价请求被拒绝，不生成买卖建议。\n过早截止日期返回 M；无金融连接时明确展示历史样本与运行模式。")
]
def stamp(t):return f"{t//3600:02}:{t//60%60:02}:{t%60:02},000"
subtitles=[];concat=[];ass_events=[];t=0
def ass_stamp(t):return f"{t//3600}:{t//60%60:02}:{t%60:02}.00"
for i,(file,duration,caption) in enumerate(scenes,1):
 p=ROOT/"docs/screenshots"/file
 assert p.exists(),p
 concat.extend([f"file '{p}'",f"duration {duration}"])
 subtitles.append(f"{i}\n{stamp(t)} --> {stamp(t+duration)}\n{caption}\n")
 ass_events.append(f"Dialogue: 0,{ass_stamp(t)},{ass_stamp(t+duration)},Default,,0,0,0,,"+caption.replace('\n',r'\N'))
 t+=duration
concat.append(f"file '{ROOT/'docs/screenshots'/scenes[-1][0]}'")
(WORK/"scenes.txt").write_text("\n".join(concat)+"\n")
subs=ROOT/"docs/demo_zh.srt";subs.write_text("\n".join(subtitles))
out=ROOT/"docs/ChainScope_Task1_demo.mp4"
ass=WORK/'captions.ass'
ass.write_text('[Script Info]\nPlayResX: 1280\nPlayResY: 820\nWrapStyle: 0\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Default,Heiti SC,24,&H00FFFFFF,&H00FFFFFF,&H00101B2C,&H00101B2C,0,0,0,0,100,100,0,0,1,0,0,2,40,40,20,1\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n'+'\n'.join(ass_events)+'\n')
filter=f"fps=24,pad=iw:ih+100:0:0:color=0x101b2c,ass='{ass}':fontsdir='/System/Library/Fonts'"
subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),"-hide_banner","-loglevel","error","-y","-f","concat","-safe","0","-i",str(WORK/"scenes.txt"),"-vf",filter,"-t",str(t),"-c:v","libx264","-crf","24","-preset","fast","-pix_fmt","yuv420p","-movflags","+faststart",str(out)],check=True)
print(f"Created {out} · {t}s · {out.stat().st_size} bytes")
