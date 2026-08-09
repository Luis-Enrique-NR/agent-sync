"use client";

import {
  createContext,
  type Dispatch,
  type SetStateAction,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

export interface ProfileData {
  name: string;
  email: string;
  accountType: "personal" | "company";
  role: string;
}

interface AuthState {
  profile: ProfileData;
  signedIn: boolean;
  authReady: boolean;
  setProfile: Dispatch<SetStateAction<ProfileData>>;
  signIn: (profile: ProfileData) => void;
  signOut: () => void;
  saveProfile: (profile: ProfileData) => void;
}

const STORAGE_KEY = "agentsync-profile-demo-v1";
const initialProfile: ProfileData = {
  name: "Valentina R.",
  email: "valentina@agentsync.demo",
  accountType: "personal",
  role: "Propietaria del agente",
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [profile, setProfile] = useState<ProfileData>(initialProfile);
  const [signedIn, setSignedIn] = useState(false);
  const [authReady, setAuthReady] = useState(false);

  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored) as {
          profile?: ProfileData;
          signedIn?: boolean;
        };
        if (parsed.profile) setProfile(parsed.profile);
        if (typeof parsed.signedIn === "boolean") setSignedIn(parsed.signedIn);
      }
    } catch {
      // Si el dato local está dañado, la demo usa una sesión nueva.
    } finally {
      setAuthReady(true);
    }
  }, []);

  const persist = useCallback((nextProfile: ProfileData, nextSignedIn: boolean) => {
    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ profile: nextProfile, signedIn: nextSignedIn }),
      );
    } catch {
      // La demo continúa en memoria cuando el almacenamiento no está disponible.
    }
  }, []);

  const signIn = useCallback(
    (nextProfile: ProfileData) => {
      setProfile(nextProfile);
      setSignedIn(true);
      persist(nextProfile, true);
    },
    [persist],
  );

  const signOut = useCallback(() => {
    setSignedIn(false);
    persist(profile, false);
  }, [persist, profile]);

  const saveProfile = useCallback(
    (nextProfile: ProfileData) => {
      setProfile(nextProfile);
      persist(nextProfile, signedIn);
    },
    [persist, signedIn],
  );

  const value = useMemo(
    () => ({
      profile,
      signedIn,
      authReady,
      setProfile,
      signIn,
      signOut,
      saveProfile,
    }),
    [profile, signedIn, authReady, signIn, signOut, saveProfile],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth debe usarse dentro de AuthProvider");
  return context;
}
