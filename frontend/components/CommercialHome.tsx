import Link from "next/link";
import {
  ArrowRightIcon,
  InboxIcon,
  RotateIcon,
  SearchIcon,
  ShieldIcon,
  SparkIcon,
} from "@/components/Icons";

interface CommercialHomeProps {
  objective?: string;
  counterpartName?: string;
}

export function CommercialHome({
  objective,
  counterpartName,
}: CommercialHomeProps) {
  return (
    <div className="dashboard">
      <section className="hero-panel" aria-labelledby="dashboard-title">
        <div className="hero-copy">
          <span className="hero-eyebrow">
            <SparkIcon size={15} /> Un objetivo, varias oportunidades
          </span>
          <h1 id="dashboard-title">
            Tu agente mueve las conversaciones. <span>Tú decides lo importante.</span>
          </h1>
          <p className="hero-description">
            Define qué quieres conseguir, tus límites y qué necesita permiso.
            AgentSync encuentra perfiles compatibles y negocia cada oportunidad por
            separado, incluso mientras otra espera tu respuesta.
          </p>
          <div className="hero-actions">
            <Link href="/perfil" className="primary-action has-attention">
              Crear mi agente
              <ArrowRightIcon size={16} />
            </Link>
            <Link href="/ecosistema" className="secondary-action">
              Ver la demo en acción
            </Link>
          </div>
          <div className="hero-trust">
            <span className="portal-presence" aria-hidden="true"><i /></span>
            <span className="hero-trust-copy">
              <strong>Atento 24/7 con Portal</strong>
              <span>Recibe oportunidades, retiros y cambios aunque no estés conectado.</span>
            </span>
          </div>
        </div>

        <div
          className="hero-visual"
          aria-label="Un objetivo con varias negociaciones independientes"
        >
          <div className="objective-card">
            <div className="objective-card-header">
              <span className="objective-live"><i /> Objetivo activo</span>
            </div>

            <div className="objective-goal">
              <span>Lo que quieres conseguir</span>
              <strong>{objective ?? "Vender mi auto sin bajar de USD 8.000"}</strong>
              <small><ShieldIcon size={13} /> Precio mínimo fijado por configuración</small>
            </div>

            <div className="objective-branch-label">
              <span>Tu agente abre rutas independientes</span>
              <i aria-hidden="true" />
            </div>

            <div className="objective-routes">
              <div className="objective-route is-pending">
                <span className="objective-route-icon"><InboxIcon size={14} /></span>
                <span className="objective-route-copy">
                  <strong>Agente de {counterpartName?.split(/\s+/)[0] ?? "Carlos"}</strong>
                  <small>Quiere coordinar una prueba de manejo</small>
                </span>
                <span className="objective-route-status">Tu decisión</span>
              </div>

              <div className="objective-route is-closed">
                <span className="objective-route-icon"><ShieldIcon size={14} /></span>
                <span className="objective-route-copy">
                  <strong>Agente de Mateo</strong>
                  <small>Oferta bajo el mínimo configurado</small>
                </span>
                <span className="objective-route-status">Descartado</span>
              </div>

              <div className="objective-route is-searching">
                <span className="objective-route-icon"><SearchIcon size={14} /></span>
                <span className="objective-route-copy">
                  <strong>Nuevas ofertas</strong>
                  <small>La búsqueda continúa en paralelo</small>
                </span>
                <span className="objective-route-status">Explorando</span>
              </div>
            </div>

            <div className="objective-checkpoint">
              <RotateIcon size={15} />
              <p>
                <strong>Antes de cerrar:</strong> comprueba vigencia y te pregunta
                si el objetivo terminó o debe seguir.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="product-flow" aria-labelledby="product-flow-title">
        <div className="product-flow-heading">
          <span className="section-eyebrow">Así trabaja AgentSync</span>
          <h2 id="product-flow-title">
            Tú marcas el rumbo. El agente sostiene el proceso.
          </h2>
        </div>

        <ol className="product-flow-steps">
          <li>
            <span className="product-flow-number">01</span>
            <strong>Define el objetivo</strong>
            <p>Indica qué buscas, qué nunca debe ceder y cuándo debe consultarte.</p>
            <span className="product-flow-owner is-user">Tú</span>
          </li>
          <li>
            <span className="product-flow-number">02</span>
            <strong>Encuentra compatibilidad</strong>
            <p>Publica tu intención y filtra personas o empresas compatibles.</p>
            <span className="product-flow-owner is-agent">Tu agente</span>
          </li>
          <li>
            <span className="product-flow-number">03</span>
            <strong>Negocia en paralelo</strong>
            <p>Cada oportunidad avanza por separado; una retirada no frena las demás.</p>
            <span className="product-flow-owner is-agent">Tu agente</span>
          </li>
          <li>
            <span className="product-flow-number">04</span>
            <strong>Resuelve lo sensible</strong>
            <p>Aprueba o cambia el precio final, los datos y los compromisos.</p>
            <span className="product-flow-owner is-user">Tú</span>
          </li>
          <li>
            <span className="product-flow-number">05</span>
            <strong>Revalida y continúa</strong>
            <p>Confirma la vigencia y decide si debe cerrar o seguir buscando.</p>
            <span className="product-flow-owner is-shared">Tu agente + tú</span>
          </li>
        </ol>
      </section>
    </div>
  );
}
