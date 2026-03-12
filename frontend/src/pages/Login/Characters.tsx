import React from 'react'

export type CharacterMood = 'idle' | 'typing' | 'password' | 'peek' | 'success' | 'error'

interface CharactersProps {
  mouseX: number // -1 ~ 1
  mouseY: number // -1 ~ 1
  mood: CharacterMood
}

/** 眼睛组件：眼白 + 瞳孔，瞳孔跟随鼠标 */
function Eye({ cx, cy, r, px, py, dark, covered }: {
  cx: number; cy: number; r: number; px: number; py: number; dark?: boolean; covered?: boolean
}) {
  if (covered) {
    return (
      <g>
        <line
          x1={cx - r} y1={cy} x2={cx + r} y2={cy}
          stroke={dark ? '#333' : '#fff'} strokeWidth={r * 0.6} strokeLinecap="round"
        />
      </g>
    )
  }
  const pupilR = r * 0.45
  return (
    <g>
      <circle cx={cx} cy={cy} r={r} fill={dark ? '#1a1a1a' : '#fff'} />
      <circle cx={cx + px} cy={cy + py} r={pupilR} fill={dark ? '#fff' : '#1a1a1a'} />
    </g>
  )
}

/**
 * 四个卡通人物（紫、黑、黄、橙）
 * 层叠（从后到前）：紫 → 黑 → 黄 → 橙
 */
export default function Characters({ mouseX, mouseY, mood }: CharactersProps) {
  // 瞳孔偏移（大幅增加跟随感）
  const px = mouseX * 5
  const py = mouseY * 4

  const coverEyes = mood === 'password'
  const lookAway = mood === 'peek'
  const smile = mood === 'success'
  const sad = mood === 'error'

  // 扭头参数（查看密码时更夸张）
  const headTilt = lookAway ? -25 : mouseX * 3
  const headShift = lookAway ? -20 : 0

  // 整体微倾斜跟随鼠标
  const bodyTilt = lookAway ? -8 : mouseX * 2

  return (
    <svg viewBox="0 0 420 410" width="100%" height="100%" style={{ overflow: 'visible' }}>
      <defs>
        <style>{`
          .char-body { transition: transform 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94); }
          .char-face { transition: transform 0.25s ease-out; }
        `}</style>
      </defs>

      {/* ============ 1. 紫色矩形（最高，后排左） ============ */}
      <g className="char-body" transform={`translate(115, 25) rotate(${bodyTilt * 0.7}, 60, 150)`}>
        <rect x="0" y="0" width="120" height="290" rx="20" fill="#7B5CFA" />
        <g className="char-face" transform={`translate(${headShift * 0.8}, 0) rotate(${headTilt * 0.3}, 60, 70)`}>
          <Eye cx={35} cy={68} r={10} px={px * 0.9} py={py * 0.9} covered={coverEyes} />
          <Eye cx={85} cy={68} r={10} px={px * 0.9} py={py * 0.9} covered={coverEyes} />
          {smile ? (
            <path d="M 35,108 Q 60,132 85,108" fill="none" stroke="#fff" strokeWidth="3" strokeLinecap="round" />
          ) : sad ? (
            <path d="M 35,125 Q 60,105 85,125" fill="none" stroke="#fff" strokeWidth="3" strokeLinecap="round" />
          ) : (
            <line x1="40" y1="112" x2="80" y2="112" stroke="#fff" strokeWidth="3" strokeLinecap="round" />
          )}
        </g>
      </g>

      {/* ============ 2. 黑色矩形（中等高，中间偏右） ============ */}
      <g className="char-body" transform={`translate(215, 115) rotate(${bodyTilt * 0.4}, 48, 105)`}>
        <rect x="0" y="0" width="95" height="210" rx="16" fill="#2D2D2D" />
        <g className="char-face" transform={`translate(${headShift * 0.6}, 0) rotate(${headTilt * 0.25}, 48, 55)`}>
          <Eye cx={28} cy={55} r={9} px={px * 0.8} py={py * 0.8} covered={coverEyes} />
          <Eye cx={67} cy={55} r={9} px={px * 0.8} py={py * 0.8} covered={coverEyes} />
          {smile ? (
            <path d="M 30,90 Q 48,110 66,90" fill="none" stroke="#fff" strokeWidth="3" strokeLinecap="round" />
          ) : sad ? (
            <path d="M 30,105 Q 48,88 66,105" fill="none" stroke="#fff" strokeWidth="3" strokeLinecap="round" />
          ) : (
            <line x1="33" y1="95" x2="62" y2="95" stroke="#fff" strokeWidth="2.5" strokeLinecap="round" />
          )}
        </g>
      </g>

      {/* ============ 3. 黄色拱门（矮个，右后） ============ */}
      <g className="char-body" transform={`translate(275, 200) rotate(${bodyTilt * 0.5}, 55, 70)`}>
        <path d="M 0,140 Q 0,-15 55,-15 Q 110,-15 110,140 Z" fill="#F5C542" />
        <g className="char-face" transform={`translate(${headShift * 0.5}, 0) rotate(${headTilt * 0.35}, 55, 50)`}>
          <Eye cx={30} cy={55} r={8} px={px * 0.7} py={py * 0.7} dark covered={coverEyes} />
          <Eye cx={80} cy={55} r={8} px={px * 0.7} py={py * 0.7} dark covered={coverEyes} />
          {smile ? (
            <path d="M 33,88 Q 55,108 77,88" fill="none" stroke="#333" strokeWidth="2.5" strokeLinecap="round" />
          ) : sad ? (
            <path d="M 33,102 Q 55,85 77,102" fill="none" stroke="#333" strokeWidth="2.5" strokeLinecap="round" />
          ) : (
            <line x1="38" y1="92" x2="72" y2="92" stroke="#333" strokeWidth="2.5" strokeLinecap="round" />
          )}
        </g>
      </g>

      {/* ============ 4. 橙色半圆（最前面，最底部） ============ */}
      <g className="char-body" transform={`translate(50, 210) rotate(${bodyTilt * 0.3}, 140, 100)`}>
        <path d="M 0,200 A 140,140 0 0,1 280,200 L 0,200 Z" fill="#F5811F" />
        <g className="char-face" transform={`translate(${headShift * 0.3}, 0) rotate(${headTilt * 0.2}, 140, 120)`}>
          <Eye cx={85} cy={118} r={11} px={px} py={py} dark covered={coverEyes} />
          <Eye cx={195} cy={118} r={11} px={px} py={py} dark covered={coverEyes} />
          {smile ? (
            <path d="M 105,160 Q 140,192 175,160" fill="none" stroke="#333" strokeWidth="4" strokeLinecap="round" />
          ) : sad ? (
            <path d="M 105,180 Q 140,155 175,180" fill="none" stroke="#333" strokeWidth="4" strokeLinecap="round" />
          ) : (
            <ellipse cx="140" cy="165" rx="7" ry="6" fill="#333" />
          )}
        </g>
      </g>
    </svg>
  )
}
