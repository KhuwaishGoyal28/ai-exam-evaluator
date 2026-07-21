/**
 * Animated circular score ring for total score display.
 */
import { useEffect, useState } from 'react';
import { clsx } from 'clsx';

interface ScoreRingProps {
  score: number;
  maxScore: number;
  grade: string;
  gradeColor: string;
}

const RADIUS = 52;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

export function ScoreRing({ score, maxScore, grade, gradeColor }: ScoreRingProps) {
  const [animated, setAnimated] = useState(false);
  const pct = maxScore > 0 ? score / maxScore : 0;
  const offset = CIRCUMFERENCE * (1 - (animated ? pct : 0));

  useEffect(() => {
    const t = setTimeout(() => setAnimated(true), 150);
    return () => clearTimeout(t);
  }, []);

  const strokeColor = pct >= 0.8 ? '#10b981' : pct >= 0.6 ? '#6366f1' : pct >= 0.4 ? '#f59e0b' : '#f43f5e';

  return (
    <div className="relative flex items-center justify-center">
      <svg width="130" height="130" className="-rotate-90">
        {/* Track */}
        <circle
          cx="65" cy="65" r={RADIUS}
          fill="none"
          stroke="#f1f5f9"
          strokeWidth="10"
        />
        {/* Fill */}
        <circle
          cx="65" cy="65" r={RADIUS}
          fill="none"
          stroke={strokeColor}
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={CIRCUMFERENCE}
          strokeDashoffset={offset}
          className="score-ring-track"
          style={{ filter: `drop-shadow(0 0 6px ${strokeColor}55)` }}
        />
      </svg>
      {/* Inner text */}
      <div className="absolute flex flex-col items-center justify-center">
        <span className="text-2xl font-black text-surface-900 tabular-nums leading-none">
          {score}
        </span>
        <span className="text-xs text-surface-400 tabular-nums">/{maxScore}</span>
        <span className={clsx('mt-1 text-xl font-black', gradeColor)}>{grade}</span>
      </div>
    </div>
  );
}
