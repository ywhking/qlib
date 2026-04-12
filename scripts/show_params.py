import argparse
import qlib
from qlib.workflow import R
from qlib.utils.mod import get_callable_kwargs
parser = argparse.ArgumentParser()
parser.add_argument("--experiment_id", required=True, help="Experiment ID")
parser.add_argument("--recorder_id", required=True, help="Recorder ID")
args = parser.parse_args()
qlib.init(provider_uri="~/.qlib/qlib_data/tushare_data")
exp = R.get_exp(experiment_id=args.experiment_id)
rec = R.get_recorder(recorder_id=args.recorder_id)
model = rec.load_object("params.pkl")
task = rec.load_object("task")
importance = model.model.feature_importance(importance_type="gain")
lgb_features = model.model.feature_name()
handler_config = task["dataset"]["kwargs"]["handler"]
handler_cls, handler_kwargs = get_callable_kwargs(handler_config)
handler = handler_cls(instruments="all", start_time="2020-01-01", end_time="2020-01-02",
                      init_data=False, **{k: v for k, v in handler_kwargs.items()
                                          if k not in ("instruments", "start_time", "end_time",
                                                       "filter_pipe", "fit_start_time", "fit_end_time")})
feature_names = list(handler.data_loader.fields["feature"][1])
name_map = {f"Column_{i}": feature_names[i] for i in range(min(len(feature_names), len(lgb_features)))}
total_gain = sum(importance)
sorted_features = sorted(zip(lgb_features, importance), key=lambda x: -x[1])
print(f"总特征数: {len(lgb_features)}\n")
print(f"{'排名':>4}  {'特征名':<25} {'内部名':<15} {'Gain':>12} {'占比':>8}")
print("-" * 70)
for rank, (f, imp) in enumerate(sorted_features, 1):
    real = name_map.get(f, f)
    pct = imp / total_gain * 100 if total_gain > 0 else 0
    print(f"{rank:>4}  {real:<25} {f:<15} {imp:>12.1f} {pct:>7.2f}%")
print(f"\nGain 为 0 的特征数: {sum(1 for _, imp in sorted_features if imp == 0)}")