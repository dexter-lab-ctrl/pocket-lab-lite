import React,{useId} from 'react';
import './liteSafeForms.css';
import { LiteConsequenceSummary } from '../LiteUx.jsx';
/** Presentation and semantics only: server remains owner of authorization and validation. */
export function LiteField({label,hint='',error='',required=false,id,children,className=''}) {const generated=useId();const fieldId=id||`lite-field-${generated}`;const detail=`${fieldId}-detail`;return <div className={`lite-safe-field ${className}`.trim()}><label htmlFor={fieldId}>{label}{required?' *':''}</label>{React.isValidElement(children)?React.cloneElement(children,{id:fieldId,required:required || Boolean(children.props.required),'aria-invalid':Boolean(error),'aria-describedby':hint||error?detail:children.props['aria-describedby']}):children}{hint||error?<small id={detail} role={error?'alert':undefined}>{error||hint}</small>:null}</div>}
export function LiteConfirmationSummary({title='Before continuing',consequences=[],warning=''}) {const visible=(Array.isArray(consequences)?consequences:[]).filter(Boolean).slice(0,6);if(!visible.length&&!warning)return null;return <section className="lite-safe-confirmation" aria-label={title}><h3>{title}</h3>{visible.length?<ul>{visible.map((text,i)=><li key={i}>{String(text)}</li>)}</ul>:null}{warning?<p>{warning}</p>:null}</section>}

/** A single presentation contract; protected handlers retain control of the actual mutation. */
export function LiteProtectedConfirmation({value,children}){
  if(!value || typeof value!=='object')return null;
  return <div className="lite-safe-protected-confirmation" data-lite-confirmation-contract="server-owned">
    <LiteConsequenceSummary value={value}/>
    {children}
  </div>;
}
