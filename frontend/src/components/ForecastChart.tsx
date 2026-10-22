import type { ForecastPoint } from "../api/contracts";

export function ForecastChart({ points }: { points: ForecastPoint[] }) {
  if (points.length < 2) {
    return <div className="empty-chart">Projection indisponible</div>;
  }

  const values = points.map((point) => point.balance);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const width = 720;
  const height = 210;
  const pad = 16;
  const coordinates = points.map((point, index) => ({
    x: pad + (index / (points.length - 1)) * (width - pad * 2),
    y: pad + ((max - point.balance) / range) * (height - pad * 2),
  }));
  const line = coordinates.map(({ x, y }) => `${x},${y}`).join(" ");
  const fill = `${pad},${height - pad} ${line} ${width - pad},${height - pad}`;

  return (
    <div className="forecast-chart">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Projection de trésorerie">
        <defs>
          <linearGradient id="forecastFill" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="var(--s-5c78ff)" stopOpacity="0.24" />
            <stop offset="100%" stopColor="var(--s-5c78ff)" stopOpacity="0" />
          </linearGradient>
        </defs>
        {[0.2, 0.5, 0.8].map((ratio) => (
          <line className="grid-line" key={ratio} x1="0" x2={width} y1={height * ratio} y2={height * ratio} />
        ))}
        <polygon fill="url(#forecastFill)" points={fill} />
        <polyline className="forecast-line" fill="none" points={line} />
        {coordinates.filter((_, index) => index % Math.max(1, Math.floor(points.length / 6)) === 0).map(({ x, y }, index) => (
          <circle className="forecast-dot" cx={x} cy={y} key={`${x}-${index}`} r="4" />
        ))}
      </svg>
      <div className="chart-axis">
        <span>{points[0]?.label}</span>
        <span>{points.at(-1)?.label}</span>
      </div>
    </div>
  );
}
