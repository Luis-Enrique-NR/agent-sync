"use client";

import { useState } from "react";
import { type ProfileData, useAuth } from "@/lib/auth";
import {
  ArrowRightIcon,
  CardIcon,
  CheckIcon,
  LockIcon,
  MailIcon,
  ShieldIcon,
  UserIcon,
} from "@/components/Icons";

type AuthMode = "login" | "register";

export function ProfileView() {
  const {
    profile,
    setProfile,
    signedIn,
    authReady,
    signIn,
    signOut,
    saveProfile,
  } = useAuth();
  const [authMode, setAuthMode] = useState<AuthMode>("login");
  const [password, setPassword] = useState("");
  const [saved, setSaved] = useState(false);

  const updateField = <Key extends keyof ProfileData>(
    key: Key,
    value: ProfileData[Key],
  ) => {
    setProfile((current) => ({ ...current, [key]: value }));
    setSaved(false);
  };

  if (!authReady) {
    return (
      <div className="auth-page auth-page-loading" role="status" aria-live="polite">
        Preparando tu cuenta…
      </div>
    );
  }

  if (!signedIn) {
    return (
      <div className="auth-page">
        <section className="auth-card" aria-labelledby="auth-title">
          <span className="section-eyebrow">Tu espacio en AgentSync</span>
          <h1 id="auth-title">
            {authMode === "login" ? "Vuelve a tus negociaciones" : "Crea tu cuenta"}
          </h1>
          <p>
            {authMode === "login"
              ? "Ingresa para revisar lo que tu agente avanzó y las decisiones que dejó para ti."
              : "Empieza con el plan Piloto. Podrás configurar tu primer agente después de registrarte."}
          </p>

          <div className="auth-tabs" role="tablist" aria-label="Acceso a la cuenta">
            <button
              type="button"
              role="tab"
              aria-selected={authMode === "login"}
              className={authMode === "login" ? "is-active" : ""}
              onClick={() => setAuthMode("login")}
            >
              Ingresar
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={authMode === "register"}
              className={authMode === "register" ? "is-active" : ""}
              onClick={() => setAuthMode("register")}
            >
              Crear cuenta
            </button>
          </div>

          <form
            className="auth-form"
            onSubmit={(event) => {
              event.preventDefault();
              signIn(profile);
              setPassword("");
            }}
          >
            <div
              className={`auth-optional-field ${authMode === "register" ? "is-open" : ""}`}
              aria-hidden={authMode !== "register"}
            >
              <div>
                <label>
                  <span>Nombre</span>
                  <span className="field-with-icon">
                    <UserIcon size={17} />
                    <input
                      value={profile.name}
                      onChange={(event) => updateField("name", event.target.value)}
                      placeholder="Tu nombre"
                      disabled={authMode !== "register"}
                      required={authMode === "register"}
                    />
                  </span>
                </label>
              </div>
            </div>

            <label>
              <span>Correo electrónico</span>
              <span className="field-with-icon">
                <MailIcon size={17} />
                <input
                  type="email"
                  value={profile.email}
                  onChange={(event) => updateField("email", event.target.value)}
                  placeholder="nombre@correo.com"
                  required
                />
              </span>
            </label>

            <label>
              <span>Contraseña</span>
              <span className="field-with-icon">
                <LockIcon size={17} />
                <input
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="Mínimo 8 caracteres"
                  minLength={8}
                  required
                />
              </span>
            </label>

            <button type="submit" className="auth-submit">
              {authMode === "login" ? "Ingresar" : "Crear mi cuenta"}
              <ArrowRightIcon size={16} />
            </button>
          </form>

          <small className="auth-demo-note">
            Acceso simulado: los datos permanecen únicamente en este navegador.
          </small>
        </section>

        <aside className="auth-side-note">
          <span><ShieldIcon size={18} /></span>
          <div>
            <strong>Tu agente puede negociar. Tu cuenta conserva el control.</strong>
            <p>Los límites y las decisiones sensibles siguen vinculados a ti.</p>
          </div>
        </aside>
      </div>
    );
  }

  return (
    <div className="profile-page">
      <header className="page-heading profile-heading">
        <div>
          <span className="section-eyebrow">Cuenta</span>
          <h1>Tu perfil en AgentSync</h1>
          <p>
            Personaliza cómo apareces en la plataforma y consulta el plan activo
            de este proyecto.
          </p>
        </div>
        <button
          type="button"
          className="profile-logout"
          onClick={() => {
            signOut();
          }}
        >
          Cerrar sesión
        </button>
      </header>

      <div className="profile-layout">
        <section className="profile-card" aria-labelledby="personal-data-title">
          <div className="profile-identity">
            <span className="profile-large-avatar">
              {profile.name
                .split(/\s+/)
                .slice(0, 2)
                .map((part) => part[0])
                .join("")
                .toUpperCase() || "AS"}
            </span>
            <div>
              <h2 id="personal-data-title">Información personal</h2>
              <p>Estos datos identifican a la persona detrás del agente.</p>
            </div>
          </div>

          <form
            className="profile-form"
            onSubmit={(event) => {
              event.preventDefault();
              saveProfile(profile);
              setSaved(true);
            }}
          >
            <div className="profile-field-grid">
              <label>
                <span>Nombre</span>
                <input
                  value={profile.name}
                  onChange={(event) => updateField("name", event.target.value)}
                  required
                />
              </label>
              <label>
                <span>Correo electrónico</span>
                <input
                  type="email"
                  value={profile.email}
                  onChange={(event) => updateField("email", event.target.value)}
                  required
                />
              </label>
              <label>
                <span>Tipo de cuenta</span>
                <select
                  value={profile.accountType}
                  onChange={(event) =>
                    updateField(
                      "accountType",
                      event.target.value as ProfileData["accountType"],
                    )
                  }
                >
                  <option value="personal">Personal</option>
                  <option value="company">Empresa</option>
                </select>
              </label>
              <label>
                <span>Rol</span>
                <input
                  value={profile.role}
                  onChange={(event) => updateField("role", event.target.value)}
                  placeholder="Ej.: Responsable de compras"
                />
              </label>
            </div>

            <div className="profile-form-footer">
              <button type="submit" className="profile-save">Guardar cambios</button>
              {saved ? (
                <span className="profile-saved" role="status">
                  <CheckIcon size={14} /> Cambios guardados
                </span>
              ) : null}
            </div>
          </form>
        </section>

        <aside className="plan-card" aria-labelledby="plan-title">
          <div className="plan-card-top">
            <span className="plan-icon"><CardIcon size={19} /></span>
            <span className="plan-status">Plan activo</span>
          </div>
          <span className="plan-kicker">Tu plan del proyecto</span>
          <h2 id="plan-title">Piloto</h2>
          <p className="plan-price"><strong>$0</strong> durante la validación</p>
          <p className="plan-description">
            Diseñado para probar el ciclo completo antes de elegir un plan de pago.
          </p>

          <ul className="plan-features">
            <li><CheckIcon size={15} /> Agentes para escenarios B2B y P2P</li>
            <li><CheckIcon size={15} /> Decisiones sensibles con control humano</li>
            <li><CheckIcon size={15} /> Historial y trazabilidad de negociaciones</li>
            <li><CheckIcon size={15} /> Integraciones simuladas para la demo</li>
          </ul>

          <button type="button" className="plan-button" disabled>
            Gestión de planes próximamente
          </button>
        </aside>
      </div>

      <div className="profile-security-note">
        <ShieldIcon size={18} />
        <span>
          <strong>Cuenta de demostración.</strong> La autenticación y el plan son
          simulados; no se envía información a servicios externos.
        </span>
      </div>
    </div>
  );
}
