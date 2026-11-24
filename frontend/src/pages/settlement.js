import {datasetField, feedback, field} from '../components/common/fields.js';
import {empty, metrics, panel, pill} from '../components/common/panels.js';
import {table} from '../components/common/table.js';
import {SETTLEMENT} from '../constants/enums.js';
import {handler, poll} from '../hooks/action.js';
import {session} from '../stores/session.js';
import {workspace} from '../stores/workspace.js';
import {button, el, link, p} from '../utils/dom.js';
import {date, money} from '../utils/format.js';

const totalsTable = totals => table([
  {key:'channel', label:'招生渠道'},
  {label:'本次差额', render:row=>money(row.delta_fen)},
  {label:'累计入账', render:row=>money(row.cumulative_fen)},
], totals, {caption:'渠道合计差额'});

const linesTable = lines => table([
  {key:'learner_id', label:'学员编号'},
  {key:'channel', label:'招生渠道'},
  {label:'分摊金额', render:row=>money(row.amount_fen)},
], lines, {caption:'逐人分摊明细'});

function detailPanel(job, refresh) {
  const finished = !['queued','running'].includes(job.status);
  if (!finished) {
    const original = location.hash;
    const status = el('p',{role:'status'},'后台正在结算，完成后会自动展示。');
    poll(()=>workspace.getSettlement(job.id),item=>!['queued','running'].includes(item.status),()=>location.hash===original)
      .then(result=>{if (result && status.isConnected && location.hash===original) refresh();
        else if(status.isConnected) status.textContent='仍在执行，请点击刷新检查。';})
      .catch(error=>{if(status.isConnected) status.textContent=error.message;});
    return panel(`结算批次 #${job.id}`, pill(SETTLEMENT[job.status],job.status), status,
      button('刷新',{class:'quiet',onClick:refresh}));
  }
  if (job.status === 'failed') return panel(`结算批次 #${job.id}`, pill(SETTLEMENT[job.status],job.status), p(job.error,'feedback'));
  if (job.status === 'superseded') return panel(`结算批次 #${job.id}`, pill(SETTLEMENT[job.status],job.status),
    p('该月份已有同等或更新的数据批次入账，旧批不能倒冲，本次未入账。'));
  const delta = job.totals.reduce((sum,row)=>sum+row.delta_fen,0);
  return el('section',{class:'analysis','data-testid':'settlement-posted'},
    el('div',{class:'result-head'},p(`结算批次 #${job.id} · ${job.period}`,'eyeline'),
      el('div',{class:'actions'},pill(SETTLEMENT[job.status],job.status))),
    metrics([
      {label:'确认学员', value:job.learner_count, detail:'沿用月报确认学员口径'},
      {label:'差额合计', value:money(delta), detail:'相对上次入账的正负差额'},
      {label:'入账时间', value:date(job.finished_at)},
    ]),
    panel('渠道合计（分差额与累计）', totalsTable(job.totals)),
    panel('逐人分摊明细', linesTable(job.lines),
      job.line_count > job.lines.length && p(`仅显示前 ${job.lines.length} 条，共 ${job.line_count} 条。`,'subtle')));
}

export async function settlementPage(route, refresh) {
  const {spec, datasets} = workspace;
  if (!session.canWrite) return panel(spec.pages[6], empty('渠道服务费结算仅向分析员和复核主管开放。','#overview',spec.pages[0]));
  const runs = await workspace.settlements();
  const error = feedback();
  const submit = button('发起月结',{type:'submit',class:'primary','data-testid':'start-settlement'});
  const form = el('form',{class:'fields','data-testid':'settlement-form',onSubmit:handler(submit,error,async event=>{
    const data = new FormData(event.target);
    const item = await workspace.startSettlement({dataset_id:Number(data.get('dataset_id')),period:data.get('period')});
    location.hash = `#settlement/${item.id}`;
  })}, datasetField(datasets),
    field({key:'period',label:'结算月份',type:'string',required:true,max_length:7,
      help:'填写 YYYY-MM。按受理日期所在的自然月结算。'},spec.params.find(param=>param.key==='period')?.default),
    el('div',{class:'actions'},submit), error);
  const selected = route.id ? await workspace.getSettlement(route.id) : null;
  const period = selected?.period || spec.params.find(param=>param.key==='period')?.default;
  const ledger = await workspace.ledger(period);
  const datasetName = id => datasets.find(item=>item.id===id)?.name || `批次 ${id}`;
  const runList = table([
    {label:'结算', render:item=>link(`${item.period} · ${datasetName(item.dataset_id)}`,`#settlement/${item.id}`)},
    {label:'状态', render:item=>pill(SETTLEMENT[item.status],item.status)},
    {label:'发起时间', render:item=>date(item.created_at)},
  ], runs, {caption:'结算记录', empty:'首次月结后将在此显示后台状态。'});
  const ledgerPanel = panel(`${period} 入账台账`,
    ledger.entries.length ? table([
      {label:'入账', render:row=>link(`#${row.id} · ${datasetName(row.dataset_id)}`,`#settlement/${row.settlement_id}`)},
      {key:'learner_count', label:'确认学员'},
      {label:'差额合计', render:row=>money(row.totals.reduce((sum,item)=>sum+item.delta_fen,0))},
      {label:'入账时间', render:row=>date(row.created_at)},
    ], ledger.entries, {caption:'入账台账'}) : p('该月份尚未入账。','empty'),
    ledger.totals.length > 0 && el('div',{},
      p('当前渠道累计','subtle'),
      metrics(ledger.totals.map(row=>({label:row.channel, value:money(row.cumulative_fen)})))));
  return el('div',{class:'two-col'},
    el('div',{class:'wide-panel'},
      selected ? detailPanel(selected,refresh) : panel('结算记录', runList),
      selected && panel('结算记录', runList),
      ledgerPanel),
    el('aside',{class:'sidebar-panel'},
      panel('发起月结', datasets.length ? form : empty('请先导入数据。','#inputs','前往导入')),
      panel('结算口径', p(spec.settlement.fee,'eyeline'),
        el('ul',{class:'method-list'},spec.settlement.methodology.map(text=>el('li',{},text))))));
}
