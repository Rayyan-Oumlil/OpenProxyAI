import type { Scene } from '../types';
import { agents } from './agents';
import { finops } from './finops';
import { home } from './home';
import { models } from './models';
import { trust } from './trust';

export type SceneId = 'home' | 'models' | 'agents' | 'trust' | 'finops';
export const SCENES: Record<SceneId, Scene> = { home, models, agents, trust, finops };
