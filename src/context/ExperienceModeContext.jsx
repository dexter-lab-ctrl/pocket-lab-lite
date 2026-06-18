import React, { createContext, useContext, useState, useEffect } from 'react';

/**
 * ExperienceModeContext provides a simple global toggle between
 * "professional" and "simple" modes.  The default is
 * "professional", matching the existing UI.  Consumers can call
 * setExperienceMode to update the mode.  In simple mode the UI
 * presents a non‑technical, outcome‑focused experience.
 */
const ExperienceModeContext = createContext({
  experienceMode: 'professional',
  setExperienceMode: () => {},
});

export const ExperienceModeProvider = ({ children }) => {
  const [experienceMode, setExperienceMode] = useState(() => {
    // Persist the choice in localStorage so users retain their selection
    if (typeof window !== 'undefined') {
      const stored = window.localStorage.getItem('pocketlab_experience_mode');
      return stored || 'professional';
    }
    return 'professional';
  });

  useEffect(() => {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem('pocketlab_experience_mode', experienceMode);
    }
  }, [experienceMode]);

  return (
    <ExperienceModeContext.Provider value={{ experienceMode, setExperienceMode }}>
      {children}
    </ExperienceModeContext.Provider>
  );
};

export const useExperienceMode = () => useContext(ExperienceModeContext);
