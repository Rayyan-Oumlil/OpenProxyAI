import React from 'react';

import {
  VIEW_HEIGHT,
  VIEW_WIDTH,
  round,
  type Align,
  type CoverDesign,
} from './design';

const LINE = 'rgba(226, 236, 248, 0.16)';
const LINE_FAINT = 'rgba(226, 236, 248, 0.07)';
const FILL = 'rgba(226, 236, 248, 0.05)';
const ACCENT = 'rgba(53, 211, 153, 0.7)';

interface ShapeProps {
  random: () => number;
  /** Where the art is densest; text sits on the other side. */
  focusX: number;
}

function Rings({random, focusX}: ShapeProps) {
  const centerY = round(VIEW_HEIGHT * (0.35 + random() * 0.5));
  const count = 7 + Math.floor(random() * 4);
  const step = 20 + random() * 10;
  return (
    <g fill="none" strokeWidth="0.75">
      {Array.from({length: count}, (_, index) => (
        <circle
          key={index}
          cx={focusX}
          cy={centerY}
          r={round(step * (index + 1))}
          stroke={index === 2 ? ACCENT : LINE}
          opacity={round(1 - index / (count + 2))}
        />
      ))}
      <ellipse
        cx={focusX}
        cy={centerY}
        rx={round(step * 2.2)}
        ry={round(step * count)}
        stroke={LINE_FAINT}
      />
    </g>
  );
}

function Grid({random, focusX}: ShapeProps) {
  const cell = 25;
  const columns = VIEW_WIDTH / cell;
  const rows = VIEW_HEIGHT / cell;
  const focusColumn = Math.floor(focusX / cell);
  const cells = Array.from({length: 9}, () => ({
    column: Math.max(
      0,
      Math.min(columns - 1, focusColumn - 4 + Math.floor(random() * 8)),
    ),
    row: Math.floor(random() * rows),
  }));
  return (
    <g>
      <g stroke={LINE_FAINT} strokeWidth="0.5">
        {Array.from({length: columns + 1}, (_, index) => (
          <line
            key={`v${index}`}
            x1={index * cell}
            y1="0"
            x2={index * cell}
            y2={VIEW_HEIGHT}
          />
        ))}
        {Array.from({length: rows + 1}, (_, index) => (
          <line
            key={`h${index}`}
            x1="0"
            y1={index * cell}
            x2={VIEW_WIDTH}
            y2={index * cell}
          />
        ))}
      </g>
      {cells.map(({column, row}, index) => (
        <rect
          key={index}
          x={column * cell}
          y={row * cell}
          width={cell}
          height={cell}
          fill={index === 0 ? 'rgba(53, 211, 153, 0.22)' : FILL}
          stroke={index === 0 ? ACCENT : LINE}
          strokeWidth="0.5"
        />
      ))}
    </g>
  );
}

/** Many callers, one gateway, several providers: the product in one drawing. */
function Routes({random, focusX}: ShapeProps) {
  const gatewayY = round(VIEW_HEIGHT * (0.4 + random() * 0.2));
  const inputs = 4 + Math.floor(random() * 3);
  const outputs = 3 + Math.floor(random() * 2);
  const left = focusX - 150;
  const right = focusX + 130;
  const spread = (count: number, index: number): number =>
    round(((index + 1) / (count + 1)) * VIEW_HEIGHT);
  const chosen = Math.floor(random() * outputs);
  return (
    <g fill="none" strokeWidth="0.75">
      {Array.from({length: inputs}, (_, index) => {
        const y = spread(inputs, index);
        return (
          <g key={`in${index}`}>
            <path
              d={`M${left} ${y} C${focusX - 60} ${y}, ${focusX - 70} ${gatewayY}, ${focusX} ${gatewayY}`}
              stroke={LINE}
            />
            <circle cx={left} cy={y} r="2" fill={LINE} />
          </g>
        );
      })}
      {Array.from({length: outputs}, (_, index) => {
        const y = spread(outputs, index);
        const active = index === chosen;
        return (
          <g key={`out${index}`}>
            <path
              d={`M${focusX} ${gatewayY} C${focusX + 60} ${gatewayY}, ${focusX + 60} ${y}, ${right} ${y}`}
              stroke={active ? ACCENT : LINE}
            />
            <rect
              x={right}
              y={y - 5}
              width="10"
              height="10"
              rx="2"
              fill={active ? 'rgba(53, 211, 153, 0.25)' : FILL}
              stroke={active ? ACCENT : LINE}
            />
          </g>
        );
      })}
      <circle cx={focusX} cy={gatewayY} r="9" fill="#0b0d11" stroke={LINE} />
      <circle cx={focusX} cy={gatewayY} r="3" fill={ACCENT} />
    </g>
  );
}

function Discs({random, focusX}: ShapeProps) {
  const count = 5 + Math.floor(random() * 3);
  return (
    <g strokeWidth="0.75">
      {Array.from({length: count}, (_, index) => {
        const radius = round(34 + random() * 44);
        const x = round(focusX - 110 + random() * 220);
        const y = round(random() * VIEW_HEIGHT);
        return (
          <circle
            key={index}
            cx={x}
            cy={y}
            r={radius}
            fill={FILL}
            stroke={index === 1 ? ACCENT : LINE}
          />
        );
      })}
    </g>
  );
}

const SHAPES = {rings: Rings, grid: Grid, routes: Routes, discs: Discs};

function focusFor(align: Align, random: () => number): number {
  return round(
    align === 'left'
      ? VIEW_WIDTH * (0.72 + random() * 0.12)
      : VIEW_WIDTH * (0.42 + random() * 0.16),
  );
}

export default function CoverArt({design}: {design: CoverDesign}): React.JSX.Element {
  const {variant, align, random} = design;
  const Shape = SHAPES[variant];
  return (
    <svg
      viewBox={`0 0 ${VIEW_WIDTH} ${VIEW_HEIGHT}`}
      preserveAspectRatio="xMidYMid slice"
      focusable="false">
      <Shape random={random} focusX={focusFor(align, random)} />
    </svg>
  );
}
