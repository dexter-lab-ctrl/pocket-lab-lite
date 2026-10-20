import React from 'react';
import { expect, userEvent, within } from '@storybook/test';
import LiteStoryFrame, { createLiteStory } from './stories/LiteStoryFrame.jsx';

// Variants reuse the same production LiteApp + Home + PR #606 shared primitives.
export default { title: 'Pocket Lab Lite/Azure Horizon', component: LiteStoryFrame, tags: ['autodocs'] };
export const DaylightDesktop = createLiteStory('home','healthy',{theme:'daylight',viewport:'desktop'});
export const BlackDesktop = createLiteStory('home','healthy',{theme:'dark',viewport:'desktop'});
export const DaylightMobile = createLiteStory('home','healthy',{theme:'daylight',viewport:'mobile390'});
export const BlackMobile = createLiteStory('home','healthy',{theme:'dark',viewport:'mobile390'});
export const SystemPreference = createLiteStory('home','healthy',{theme:'system',viewport:'desktop'});
export const Attention = createLiteStory('home','lifecycle-attention',{theme:'dark',viewport:'desktop'});
export const Saved = createLiteStory('home','offline-saved',{theme:'dark',viewport:'mobile390'});
export const Unavailable = createLiteStory('home','api-unavailable',{theme:'daylight',viewport:'mobile360'});
export const Loading = createLiteStory('home','healthy',{theme:'dark',viewport:'mobile360',notes:'Loading behavior is exercised by mocked delayed network tests; this story uses the normal prepared projection.'});
export const Narrow = createLiteStory('home','healthy',{theme:'dark',viewport:'mobile360'});
export const LongText = createLiteStory('home','lifecycle-attention',{theme:'daylight',viewport:'mobile360',textScale:2});
export const DetailsDaylight = {
  ...createLiteStory('home','healthy',{theme:'daylight',viewport:'desktop'}),
  play: async ({ canvasElement }) => {
    await userEvent.click(await within(canvasElement).findByRole('button',{name:'Workspace details'}));
    await expect(await within(canvasElement.ownerDocument.body).findByRole('dialog',{name:/Workspace details/i})).toBeInTheDocument();
  },
};
export const DetailsBlackMobile = {
  ...createLiteStory('home','healthy',{theme:'dark',viewport:'mobile390'}),
  play: DetailsDaylight.play,
};
export const ActivityDetails = {
  ...createLiteStory('home','healthy',{theme:'dark',viewport:'desktop'}),
  play: async ({ canvasElement }) => {
    await userEvent.click(await within(canvasElement).findByRole('button',{name:/View activity/i}));
    await expect(await within(canvasElement.ownerDocument.body).findByRole('dialog',{name:/Recent activity/i})).toBeInTheDocument();
  },
};
