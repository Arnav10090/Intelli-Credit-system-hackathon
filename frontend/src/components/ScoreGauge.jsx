export default function ScoreGauge({ score = 0, grade = '?', label = '', decision = '' }) {
    const decisionColor = decision === 'APPROVE'
        ? 'var(--approve)' : decision === 'PARTIAL'
            ? 'var(--partial)' : 'var(--reject)'

    // Arc parameters
    const R = 72
    const cx = 96, cy = 96
    const startAngle = -220   // degrees, measured from 3 o'clock, going CCW
    const arcSpan = 260

    function polarToXY(angleDeg, r) {
        const rad = (angleDeg * Math.PI) / 180
        return {
            x: cx + r * Math.cos(rad),
            y: cy + r * Math.sin(rad),
        }
    }

    function describeArc(startDeg, endDeg, r) {
        const s = polarToXY(startDeg, r)
        const e = polarToXY(endDeg, r)
        const large = Math.abs(endDeg - startDeg) > 180 ? 1 : 0
        return `M ${s.x} ${s.y} A ${r} ${r} 0 ${large} 1 ${e.x} ${e.y}`
    }

    const bgStart = -220
    const bgEnd = bgStart + arcSpan

    const pct = Math.min(1, Math.max(0, score / 100))
    const fillEnd = bgStart + arcSpan * pct

    // Track width
    const TW = 10

    // Needle
    const needleAngle = bgStart + arcSpan * pct
    const nTip = polarToXY(needleAngle, R - 4)
    const nBase1 = polarToXY(needleAngle + 90, 7)
    const nBase2 = polarToXY(needleAngle - 90, 7)

    // Grade color
    const gradeColor =
        ['A+', 'A'].includes(grade) ? 'var(--approve)' :
            ['B+', 'B'].includes(grade) ? 'var(--partial)' :
                'var(--reject)'

    return (
        <svg viewBox="0 0 192 185" style={{ width: 192, height: 185 }}>
            {/* Background track */}
            <path
                d={describeArc(bgStart, bgEnd, R)}
                fill="none" stroke="var(--border)" strokeWidth={TW}
                strokeLinecap="round"
            />

            {/* Color zones (faint) */}
            <path d={describeArc(bgStart, bgStart + arcSpan * 0.35, R)}
                fill="none" stroke="var(--reject-bg)" strokeWidth={TW - 1} strokeLinecap="round" opacity={0.6} />
            <path d={describeArc(bgStart + arcSpan * 0.35, bgStart + arcSpan * 0.55, R)}
                fill="none" stroke="var(--partial-bg)" strokeWidth={TW - 1} strokeLinecap="round" opacity={0.6} />
            <path d={describeArc(bgStart + arcSpan * 0.55, bgEnd, R)}
                fill="none" stroke="var(--approve-bg)" strokeWidth={TW - 1} strokeLinecap="round" opacity={0.6} />

            {/* Fill arc */}
            {pct > 0.01 && (
                <path
                    d={describeArc(bgStart, fillEnd, R)}
                    fill="none" stroke={decisionColor} strokeWidth={TW}
                    strokeLinecap="round"
                    style={{ filter: `drop-shadow(0 0 6px ${decisionColor})` }}
                />
            )}

            {/* Needle */}
            <polygon
                points={`${nTip.x},${nTip.y} ${nBase1.x},${nBase1.y} ${nBase2.x},${nBase2.y}`}
                fill={decisionColor} opacity={0.9}
            />
            <circle cx={cx} cy={cy} r={5} fill={decisionColor} />

            {/* Score */}
            <text x={cx} y={cy - 12} textAnchor="middle"
                fill={decisionColor} fontSize={28} fontWeight={700}
                fontFamily="JetBrains Mono, monospace"
            >
                {score}
                <tspan fontSize={12} fill="var(--text-dim)" dx={4}>/ 100</tspan>
            </text>

            {/* Grade badge */}
            <rect x={cx - 35} y={cy + 54} width={70} height={24} rx={6}
                fill={gradeColor} opacity={0.15} />
            <rect x={cx - 35} y={cy + 54} width={70} height={24} rx={6}
                fill="none" stroke={gradeColor} strokeWidth={1} />
            <text x={cx} y={cy + 71} textAnchor="middle"
                fill={gradeColor} fontSize={11} fontWeight={700}
                fontFamily="JetBrains Mono, monospace"
            >Grade {grade}</text>

            {/* Labels */}
            <text x={cx - R + 4} y={cy + 22} textAnchor="middle"
                fill="var(--text-dim)" fontSize={8} fontFamily="Outfit, sans-serif">0</text>
            <text x={cx + R - 4} y={cy + 22} textAnchor="middle"
                fill="var(--text-dim)" fontSize={8} fontFamily="Outfit, sans-serif">100</text>
        </svg>
    )
}