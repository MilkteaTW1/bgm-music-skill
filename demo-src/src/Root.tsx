import React from 'react';
import {Composition} from 'remotion';
import {Demo} from './Demo';
import data from './moods.json';

export const Root: React.FC = () => (
  <Composition id="Demo" component={Demo} durationInFrames={data.frames} fps={30} width={1920} height={1080} />
);
