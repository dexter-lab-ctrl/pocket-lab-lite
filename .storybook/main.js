/** @type { import('@storybook/react-vite').StorybookConfig } */
const config = {
  stories: ['../src/lite/**/*.stories.@(js|jsx|ts|tsx)'],
  addons: [
    '@storybook/addon-essentials',
    '@storybook/addon-a11y',
    '@storybook/addon-interactions',
  ],
  framework: {
    name: '@storybook/react-vite',
    options: {},
  },
  docs: { autodocs: 'tag' },
  core: { disableTelemetry: true },
  staticDirs: ['../public'],
};

export default config;
