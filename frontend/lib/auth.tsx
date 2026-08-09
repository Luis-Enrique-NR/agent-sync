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
import { DEMO_OWNER_AGENT_ID } from "@/lib/demo";

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
  agentId: string | null;
  setProfile: Dispatch<SetStateAction<ProfileData>>;
  signIn: (profile: ProfileData, agentId: string | null) => void;
  signOut: () => void;
  saveProfile: (profile: ProfileData) => void;
  attachAgent: (agentId: string) => void;
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
  const [agentId, setAgentId] = useState<string | null>(null);
  const [authReady, setAuthReady] = useState(false);

  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored) as {
          profile?: ProfileData;
          signedIn?: boolean;
          agentId?: string | null;
        };
        if (parsed.profile) setProfile(parsed.profile);
        if (typeof parsed.signedIn === "boolean") setSignedIn(parsed.signedIn);
        if (Object.prototype.hasOwnProperty.call(parsed, "agentId")) {
          setAgentId(parsed.agentId ?? null);
        } else if (parsed.signedIn) {
          setAgentId(DEMO_OWNER_AGENT_ID);
        }
      }
    } catch {
      // Si el dato local está dañado, la demo usa una sesión nueva.
    } finally {
      setAuthReady(true);
    }
  }, []);

  const persist = useCallback((
    nextProfile: ProfileData,
    nextSignedIn: boolean,
    nextAgentId: string | null,
  ) => {
    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          profile: nextProfile,
          signedIn: nextSignedIn,
          agentId: nextAgentId,
        }),
      );
    } catch {
      // La demo continúa en memoria cuando el almacenamiento no está disponible.
    }
  }, []);

  const signIn = useCallback(
    (nextProfile: ProfileData, nextAgentId: string | null) => {
      setProfile(nextProfile);
      setSignedIn(true);
      setAgentId(nextAgentId);
      persist(nextProfile, true, nextAgentId);
    },
    [persist],
  );

  const signOut = useCallback(() => {
    setSignedIn(false);
    persist(profile, false, agentId);
  }, [agentId, persist, profile]);

  const saveProfile = useCallback(
    (nextProfile: ProfileData) => {
      setProfile(nextProfile);
      persist(nextProfile, signedIn, agentId);
    },
    [agentId, persist, signedIn],
  );

  const attachAgent = useCallback(
    (nextAgentId: string) => {
      setAgentId(nextAgentId);
      persist(profile, signedIn, nextAgentId);
    },
    [persist, profile, signedIn],
  );

  const value = useMemo(
    () => ({
      profile,
      signedIn,
      authReady,
      agentId,
      setProfile,
      signIn,
      signOut,
      saveProfile,
      attachAgent,
    }),
    [
      profile,
      signedIn,
      authReady,
      agentId,
      signIn,
      signOut,
      saveProfile,
      attachAgent,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth debe usarse dentro de AuthProvider");
  return context;
}
