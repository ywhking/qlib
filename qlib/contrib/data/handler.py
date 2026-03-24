# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from qlib.contrib.data.loader import Alpha158DL, Alpha360DL
from ...data.dataset.handler import DataHandlerLP
from ...data.dataset.processor import Processor
from ...utils import get_callable_kwargs
from ...data.dataset import processor as processor_module
from inspect import getfullargspec


def check_transform_proc(proc_l, fit_start_time, fit_end_time):
    new_l = []
    for p in proc_l:
        if not isinstance(p, Processor):
            klass, pkwargs = get_callable_kwargs(p, processor_module)
            args = getfullargspec(klass).args
            if "fit_start_time" in args and "fit_end_time" in args:
                assert (
                    fit_start_time is not None and fit_end_time is not None
                ), "Make sure `fit_start_time` and `fit_end_time` are not None."
                pkwargs.update(
                    {
                        "fit_start_time": fit_start_time,
                        "fit_end_time": fit_end_time,
                    }
                )
            proc_config = {"class": klass.__name__, "kwargs": pkwargs}
            if isinstance(p, dict) and "module_path" in p:
                proc_config["module_path"] = p["module_path"]
            new_l.append(proc_config)
        else:
            new_l.append(p)
    return new_l


_DEFAULT_LEARN_PROCESSORS = [
    {"class": "DropnaLabel"},
    {"class": "CSZScoreNorm", "kwargs": {"fields_group": "label"}},
]
_DEFAULT_INFER_PROCESSORS = [
    {"class": "ProcessInf", "kwargs": {}},
    {"class": "ZScoreNorm", "kwargs": {}},
    {"class": "Fillna", "kwargs": {}},
]


class Alpha360(DataHandlerLP):
    def __init__(
        self,
        instruments="csi500",
        start_time=None,
        end_time=None,
        freq="day",
        infer_processors=_DEFAULT_INFER_PROCESSORS,
        learn_processors=_DEFAULT_LEARN_PROCESSORS,
        fit_start_time=None,
        fit_end_time=None,
        filter_pipe=None,
        inst_processors=None,
        **kwargs,
    ):
        infer_processors = check_transform_proc(infer_processors, fit_start_time, fit_end_time)
        learn_processors = check_transform_proc(learn_processors, fit_start_time, fit_end_time)

        data_loader = {
            "class": "QlibDataLoader",
            "kwargs": {
                "config": {
                    "feature": Alpha360DL.get_feature_config(),
                    "label": kwargs.pop("label", self.get_label_config()),
                },
                "filter_pipe": filter_pipe,
                "freq": freq,
                "inst_processors": inst_processors,
            },
        }

        super().__init__(
            instruments=instruments,
            start_time=start_time,
            end_time=end_time,
            data_loader=data_loader,
            learn_processors=learn_processors,
            infer_processors=infer_processors,
            **kwargs,
        )

    def get_label_config(self):
        return ["Ref($close, -2)/Ref($close, -1) - 1"], ["LABEL0"]


class Alpha360vwap(Alpha360):
    def get_label_config(self):
        return ["Ref($vwap, -2)/Ref($vwap, -1) - 1"], ["LABEL0"]


class Alpha158(DataHandlerLP):
    def __init__(
        self,
        instruments="csi500",
        start_time=None,
        end_time=None,
        freq="day",
        infer_processors=[],
        learn_processors=_DEFAULT_LEARN_PROCESSORS,
        fit_start_time=None,
        fit_end_time=None,
        process_type=DataHandlerLP.PTYPE_A,
        filter_pipe=None,
        inst_processors=None,
        **kwargs,
    ):
        infer_processors = check_transform_proc(infer_processors, fit_start_time, fit_end_time)
        learn_processors = check_transform_proc(learn_processors, fit_start_time, fit_end_time)

        data_loader = {
            "class": "QlibDataLoader",
            "kwargs": {
                "config": {
                    "feature": self.get_feature_config(),
                    "label": kwargs.pop("label", self.get_label_config()),
                },
                "filter_pipe": filter_pipe,
                "freq": freq,
                "inst_processors": inst_processors,
            },
        }
        super().__init__(
            instruments=instruments,
            start_time=start_time,
            end_time=end_time,
            data_loader=data_loader,
            infer_processors=infer_processors,
            learn_processors=learn_processors,
            process_type=process_type,
            **kwargs,
        )

    def get_feature_config(self):
        conf = {
            "kbar": {},
            "price": {
                "windows": [0],
                "feature": ["OPEN", "HIGH", "LOW", "VWAP"],
            },
            "rolling": {},
        }
        return Alpha158DL.get_feature_config(conf)

    def get_label_config(self):
        return ["Ref($close, -2)/Ref($close, -1) - 1"], ["LABEL0"]


class Alpha158vwap(Alpha158):
    def get_label_config(self):
        return ["Ref($vwap, -2)/Ref($vwap, -1) - 1"], ["LABEL0"]
    
class Alpha158Extended(Alpha158):
    """
    扩展版 Alpha158，增加换手率、成交额、流通股等自定义特征
    保留原始 Alpha158 的 158 个特征，额外增加约 30+ 个自定义特征
    """

    def get_feature_config(self):
        """
        获取扩展特征配置
        """
        # 获取原始 Alpha158 的 158 个特征
        base_fields, base_names = super().get_feature_config()

        # 添加自定义特征
        custom_fields, custom_names = self._get_custom_features()

        # 合并
        all_fields = base_fields + custom_fields
        all_names = base_names + custom_names

        print(f"\n特征统计:")
        print(f"  - 原始 Alpha158: {len(base_names)} 个")
        print(f"  - 自定义特征: {len(custom_names)} 个")
        print(f"  - 总计: {len(all_names)} 个")

        return all_fields, all_names

    def _get_custom_features(self):
        """
        定义自定义特征
        """
        fields = []
        names = []

        # ========== 1. 换手率特征 (Turnover) - 优化 ==========
        # 近3日换手率（减少内存占用）
        for d in range(3):
            if d == 0:
                fields.append("$turnover")
            else:
                fields.append(f"Ref($turnover, {d})")
            names.append(f"TURNOVER{d}")

        # 换手率移动平均（只保留5日）
        fields.append("Mean($turnover, 5)")
        names.append("TURNOVER_MA5")

        # 换手率变化率
        fields.append("$turnover/Ref($turnover, 1)-1")
        names.append("TURNOVER_CHG")

        # ========== 2. 成交额特征 (Amount) - 简化 ==========
        # 当日成交额
        fields.append("$amount/($amount+1e-12)")
        names.append("AMOUNT0")

        # 成交额移动平均
        fields.append("Mean($amount, 5)/($amount+1e-12)")
        names.append("AMOUNT_MA5")

        # 成交额变化率
        fields.append("$amount/Ref($amount, 1)-1")
        names.append("AMOUNT_CHG1")

        # ========== 3. 流通股特征 (Outstanding Share) - 简化 ==========
        fields.append("$outstanding_share/($outstanding_share+1e-12)")
        names.append("OUTSTANDING0")

        # ========== 4. 衍生特征 - 简化 ==========
        # 成交额/成交量 = 成交均价 / 收盘价
        fields.append("$amount/($volume+1e-12)/$close")
        names.append("VWAP_CUSTOM")

        # 换手率*成交量 (资金活跃度指标)
        fields.append("$turnover*$volume/($volume+1e-12)")
        names.append("TURNOVER_VOL_ACTIVE")

        return fields, names

