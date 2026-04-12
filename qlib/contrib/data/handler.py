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
                assert fit_start_time is not None and fit_end_time is not None, (
                    "Make sure `fit_start_time` and `fit_end_time` are not None."
                )
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
        infer_processors = check_transform_proc(
            infer_processors, fit_start_time, fit_end_time
        )
        learn_processors = check_transform_proc(
            learn_processors, fit_start_time, fit_end_time
        )

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
        infer_processors = check_transform_proc(
            infer_processors, fit_start_time, fit_end_time
        )
        learn_processors = check_transform_proc(
            learn_processors, fit_start_time, fit_end_time
        )

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


class Alpha158Full(Alpha158):
    # def get_feature_config(self):
    #     base_fields, base_names = super().get_feature_config()
    #     custom_fields, custom_names = self._get_custom_features()
    #     return base_fields + custom_fields, base_names + custom_names
    _EXCLUDE_FEATURES = {
        "KMID",
        "VWAP0",
        "RANK5",
        "RANK10",
        "IMAX5",
        "IMIN5",
        "IMXD5",
        "CNTP5",
        "CNTN5",
        "CNTD5",
        "VSUMP5",
        "VSUMN5",
        "VSUMD20",
        "TOTALMV_CHG",
        "MFSM_NET",
        "MFELG_BUY_SELL",
        "KMID2",
        "IMAX10",
        "CORR5",
        "CNTP10",
        "VSUMD10",
        "MFNET_VOL0",
        "MFELG_NET",
        "KSFT2",
        "OPEN0",
        "HIGH0",
        "VMA5",
        "TRATE_CHG",
        "CIRCMV_CHG",
        "VSUMD30",
        "KUP2",
        "RESI5",
        "VSUMN30",
        "RANK20",
        "RSQR5",
    }
    
    def get_feature_config(self):
        base_fields, base_names = super().get_feature_config()
        custom_fields, custom_names = self._get_custom_features()
        all_fields = base_fields + custom_fields
        all_names = base_names + custom_names
        filtered = [(f, n) for f, n in zip(all_fields, all_names) if n not in self._EXCLUDE_FEATURES]
        if filtered:
            fields, names = zip(*filtered)
            return list(fields), list(names)

    def _get_custom_features(self):
        fields, names = [], []
        self._add_turnover_features(fields, names)
        self._add_valuation_features(fields, names)
        self._add_market_cap_features(fields, names)
        self._add_money_flow_features(fields, names)
        return fields, names

    def _add_turnover_features(self, fields, names):
        fields += [
            "$turnover_rate",
            "Ref($turnover_rate, 1)",
            "Mean($turnover_rate, 5)",
            "Mean($turnover_rate, 10)",
            "Mean($turnover_rate, 20)",
            "Std($turnover_rate, 5)",
            "Std($turnover_rate, 10)",
            "$turnover_rate/(Ref($turnover_rate, 1)+1e-12)-1",
            "$turnover_rate_f",
            "Mean($turnover_rate_f, 5)",
            "$volume_ratio",
            "Mean($volume_ratio, 5)",
        ]
        names += [
            "TRATE0",
            "TRATE1",
            "TRATE_MA5",
            "TRATE_MA10",
            "TRATE_MA20",
            "TRATE_STD5",
            "TRATE_STD10",
            "TRATE_CHG",
            "TRATEF0",
            "TRATEF_MA5",
            "VOLRATIO0",
            "VOLRATIO_MA5",
        ]

    def _add_valuation_features(self, fields, names):
        _pe_expr = "Log(Abs($pe)+1)*Sign($pe)"
        _pettm_expr = "Log(Abs($pe_ttm)+1)*Sign($pe_ttm)"
        _pb_expr = "Log(Abs($pb)+1)*Sign($pb)"
        _ps_expr = "Log(Abs($ps)+1)*Sign($ps)"
        _psttm_expr = "Log(Abs($ps_ttm)+1)*Sign($ps_ttm)"
        fields += [
            _pe_expr,
            f"Mean({_pe_expr}, 5)",
            f"Mean({_pe_expr}, 10)",
            f"Mean({_pe_expr}, 20)",
            _pettm_expr,
            f"Mean({_pettm_expr}, 5)",
            f"Mean({_pettm_expr}, 10)",
            _pb_expr,
            f"Mean({_pb_expr}, 5)",
            f"Mean({_pb_expr}, 10)",
            f"Mean({_pb_expr}, 20)",
            _ps_expr,
            _psttm_expr,
            f"Mean({_ps_expr}, 5)",
            f"Mean({_psttm_expr}, 5)",
            "$dv_ratio",
            "$dv_ttm",
            "Mean($dv_ratio, 5)",
        ]
        names += [
            "PE0",
            "PE_MA5",
            "PE_MA10",
            "PE_MA20",
            "PETTM0",
            "PETTM_MA5",
            "PETTM_MA10",
            "PB0",
            "PB_MA5",
            "PB_MA10",
            "PB_MA20",
            "PS0",
            "PSTTM0",
            "PS_MA5",
            "PSTTM_MA5",
            "DV0",
            "DVTTM0",
            "DV_MA5",
        ]

    def _add_market_cap_features(self, fields, names):
        fields += [
            "Log($total_mv+1)",
            # "Log($circ_mv+1)",
            # "$circ_mv/($total_mv+1e-12)",
            # "$float_share/($total_share+1e-12)",
            "$free_share/($total_share+1e-12)",
            # "$free_share/($float_share+1e-12)",
            # "Log($total_mv+1)-Log(Ref($total_mv, 1)+1)",
            # "Log($circ_mv+1)-Log(Ref($circ_mv, 1)+1)",
            # "Log($float_share+1)",
            # "Log($free_share+1)",
        ]
        names += [
            "TOTALMV",
            # "CIRCMV",
            # "CIRC_RATIO",
            # "FLOAT_RATIO",
            "FREE_RATIO",
            # "FLOAT_FREE_RATIO",
            # "TOTALMV_CHG",
            # "CIRCMV_CHG",
            # "LOG_FLOAT",
            # "LOG_FREE",
        ]

    def _add_money_flow_features(self, fields, names):
        _lg_net = "($buy_lg_amount+$buy_elg_amount-$sell_lg_amount-$sell_elg_amount)/($amount+1e-12)"
        _sm_net = "($buy_sm_amount-$sell_sm_amount)/($amount+1e-12)"
        _md_net = "($buy_md_amount-$sell_md_amount)/($amount+1e-12)"
        _elg_net = "($buy_elg_amount-$sell_elg_amount)/($amount+1e-12)"
        _lg_ratio = "($buy_lg_amount+$sell_lg_amount+$buy_elg_amount+$sell_elg_amount)/($amount+1e-12)"
        _sm_lg = "(($buy_sm_amount-$sell_sm_amount)-($buy_lg_amount+$buy_elg_amount-$sell_lg_amount-$sell_elg_amount))/($amount+1e-12)"
        fields += [
            "$net_mf_amount/($amount+1e-12)",
            "Mean($net_mf_amount/($amount+1e-12), 5)",
            "Mean($net_mf_amount/($amount+1e-12), 10)",
            "Mean($net_mf_amount/($amount+1e-12), 20)",
            "$net_mf_vol/($volume+1e-12)",
            "Mean($net_mf_vol/($volume+1e-12), 5)",
            "Mean($net_mf_vol/($volume+1e-12), 10)",
            _lg_net,
            f"Mean({_lg_net}, 5)",
            f"Mean({_lg_net}, 10)",
            f"Mean({_lg_net}, 20)",
            _sm_net,
            f"Mean({_sm_net}, 5)",
            f"Mean({_sm_net}, 10)",
            _md_net,
            f"Mean({_md_net}, 5)",
            f"Mean({_md_net}, 10)",
            _elg_net,
            f"Mean({_elg_net}, 5)",
            f"Mean({_elg_net}, 10)",
            _lg_ratio,
            f"Mean({_lg_ratio}, 5)",
            f"Mean({_lg_ratio}, 10)",
            _sm_lg,
            f"Mean({_sm_lg}, 5)",
            "Sum($net_mf_amount, 5)/(Sum(Abs($net_mf_amount), 5)+1e-12)",
            "Sum($net_mf_amount, 10)/(Sum(Abs($net_mf_amount), 10)+1e-12)",
            "Sum($net_mf_amount, 20)/(Sum(Abs($net_mf_amount), 20)+1e-12)",
            "Corr($close/Ref($close, 1)-1, $net_mf_amount/($amount+1e-12), 5)",
            "Corr($close/Ref($close, 1)-1, $net_mf_amount/($amount+1e-12), 10)",
            "$buy_lg_amount/($sell_lg_amount+1e-12)",
            "Mean($buy_lg_amount/($sell_lg_amount+1e-12), 5)",
            "$buy_elg_amount/($sell_elg_amount+1e-12)",
            "Mean($buy_elg_amount/($sell_elg_amount+1e-12), 5)",
            "$buy_sm_amount/($sell_sm_amount+1e-12)",
            "Mean($buy_sm_amount/($sell_sm_amount+1e-12), 5)",
        ]
        names += [
            "MFNET_AMT0",
            "MFNET_AMT_MA5",
            "MFNET_AMT_MA10",
            "MFNET_AMT_MA20",
            "MFNET_VOL0",
            "MFNET_VOL_MA5",
            "MFNET_VOL_MA10",
            "MFLG_NET",
            "MFLG_NET_MA5",
            "MFLG_NET_MA10",
            "MFLG_NET_MA20",
            "MFSM_NET",
            "MFSM_NET_MA5",
            "MFSM_NET_MA10",
            "MFMD_NET",
            "MFMD_NET_MA5",
            "MFMD_NET_MA10",
            "MFELG_NET",
            "MFELG_NET_MA5",
            "MFELG_NET_MA10",
            "MFLG_RATIO",
            "MFLG_RATIO_MA5",
            "MFLG_RATIO_MA10",
            "MF_SM_LG",
            "MF_SM_LG_MA5",
            "MFNET_MOM5",
            "MFNET_MOM10",
            "MFNET_MOM20",
            "MF_CORR5",
            "MF_CORR10",
            "MFLG_BUY_SELL",
            "MFLG_BUY_SELL_MA5",
            "MFELG_BUY_SELL",
            "MFELG_BUY_SELL_MA5",
            "MFSM_BUY_SELL",
            "MFSM_BUY_SELL_MA5",
        ]


class Alpha158Custom(Alpha158):
    def get_feature_config(self):
        custom_fields, custom_names = self._get_custom_features()
        return custom_fields, custom_names

    def _get_custom_features(self):
        fields, names = [], []
        self._add_turnover_features(fields, names)
        self._add_valuation_features(fields, names)
        self._add_market_cap_features(fields, names)
        self._add_money_flow_features(fields, names)
        return fields, names

    def _add_turnover_features(self, fields, names):
        fields += [
            "$turnover_rate",
            "Ref($turnover_rate, 1)",
            "Mean($turnover_rate, 5)",
            "Mean($turnover_rate, 10)",
            "Mean($turnover_rate, 20)",
            "Std($turnover_rate, 5)",
            "Std($turnover_rate, 10)",
            "$turnover_rate/(Ref($turnover_rate, 1)+1e-12)-1",
            "$turnover_rate_f",
            "Mean($turnover_rate_f, 5)",
            "$volume_ratio",
            "Mean($volume_ratio, 5)",
        ]
        names += [
            "TRATE0",
            "TRATE1",
            "TRATE_MA5",
            "TRATE_MA10",
            "TRATE_MA20",
            "TRATE_STD5",
            "TRATE_STD10",
            "TRATE_CHG",
            "TRATEF0",
            "TRATEF_MA5",
            "VOLRATIO0",
            "VOLRATIO_MA5",
        ]

    def _add_valuation_features(self, fields, names):
        _pe_expr = "Log(Abs($pe)+1)*Sign($pe)"
        _pettm_expr = "Log(Abs($pe_ttm)+1)*Sign($pe_ttm)"
        _pb_expr = "Log(Abs($pb)+1)*Sign($pb)"
        _ps_expr = "Log(Abs($ps)+1)*Sign($ps)"
        _psttm_expr = "Log(Abs($ps_ttm)+1)*Sign($ps_ttm)"
        fields += [
            _pe_expr,
            f"Mean({_pe_expr}, 5)",
            f"Mean({_pe_expr}, 10)",
            f"Mean({_pe_expr}, 20)",
            _pettm_expr,
            f"Mean({_pettm_expr}, 5)",
            f"Mean({_pettm_expr}, 10)",
            _pb_expr,
            f"Mean({_pb_expr}, 5)",
            f"Mean({_pb_expr}, 10)",
            f"Mean({_pb_expr}, 20)",
            _ps_expr,
            _psttm_expr,
            f"Mean({_ps_expr}, 5)",
            f"Mean({_psttm_expr}, 5)",
            "$dv_ratio",
            "$dv_ttm",
            "Mean($dv_ratio, 5)",
        ]
        names += [
            "PE0",
            "PE_MA5",
            "PE_MA10",
            "PE_MA20",
            "PETTM0",
            "PETTM_MA5",
            "PETTM_MA10",
            "PB0",
            "PB_MA5",
            "PB_MA10",
            "PB_MA20",
            "PS0",
            "PSTTM0",
            "PS_MA5",
            "PSTTM_MA5",
            "DV0",
            "DVTTM0",
            "DV_MA5",
        ]

    def _add_market_cap_features(self, fields, names):
        fields += [
            "Log($total_mv+1)",
            "Log($circ_mv+1)",
            "$circ_mv/($total_mv+1e-12)",
            "$float_share/($total_share+1e-12)",
            "$free_share/($total_share+1e-12)",
            "$free_share/($float_share+1e-12)",
            "Log($total_mv+1)-Log(Ref($total_mv, 1)+1)",
            "Log($circ_mv+1)-Log(Ref($circ_mv, 1)+1)",
            "Log($float_share+1)",
            "Log($free_share+1)",
        ]
        names += [
            "TOTALMV",
            "CIRCMV",
            "CIRC_RATIO",
            "FLOAT_RATIO",
            "FREE_RATIO",
            "FLOAT_FREE_RATIO",
            "TOTALMV_CHG",
            "CIRCMV_CHG",
            "LOG_FLOAT",
            "LOG_FREE",
        ]

    def _add_money_flow_features(self, fields, names):
        _lg_net = "($buy_lg_amount+$buy_elg_amount-$sell_lg_amount-$sell_elg_amount)/($amount+1e-12)"
        _sm_net = "($buy_sm_amount-$sell_sm_amount)/($amount+1e-12)"
        _md_net = "($buy_md_amount-$sell_md_amount)/($amount+1e-12)"
        _elg_net = "($buy_elg_amount-$sell_elg_amount)/($amount+1e-12)"
        _lg_ratio = "($buy_lg_amount+$sell_lg_amount+$buy_elg_amount+$sell_elg_amount)/($amount+1e-12)"
        _sm_lg = "(($buy_sm_amount-$sell_sm_amount)-($buy_lg_amount+$buy_elg_amount-$sell_lg_amount-$sell_elg_amount))/($amount+1e-12)"
        fields += [
            "$net_mf_amount/($amount+1e-12)",
            "Mean($net_mf_amount/($amount+1e-12), 5)",
            "Mean($net_mf_amount/($amount+1e-12), 10)",
            "Mean($net_mf_amount/($amount+1e-12), 20)",
            "$net_mf_vol/($volume+1e-12)",
            "Mean($net_mf_vol/($volume+1e-12), 5)",
            "Mean($net_mf_vol/($volume+1e-12), 10)",
            _lg_net,
            f"Mean({_lg_net}, 5)",
            f"Mean({_lg_net}, 10)",
            f"Mean({_lg_net}, 20)",
            _sm_net,
            f"Mean({_sm_net}, 5)",
            f"Mean({_sm_net}, 10)",
            _md_net,
            f"Mean({_md_net}, 5)",
            f"Mean({_md_net}, 10)",
            _elg_net,
            f"Mean({_elg_net}, 5)",
            f"Mean({_elg_net}, 10)",
            _lg_ratio,
            f"Mean({_lg_ratio}, 5)",
            f"Mean({_lg_ratio}, 10)",
            _sm_lg,
            f"Mean({_sm_lg}, 5)",
            "Sum($net_mf_amount, 5)/(Sum(Abs($net_mf_amount), 5)+1e-12)",
            "Sum($net_mf_amount, 10)/(Sum(Abs($net_mf_amount), 10)+1e-12)",
            "Sum($net_mf_amount, 20)/(Sum(Abs($net_mf_amount), 20)+1e-12)",
            "Corr($close/Ref($close, 1)-1, $net_mf_amount/($amount+1e-12), 5)",
            "Corr($close/Ref($close, 1)-1, $net_mf_amount/($amount+1e-12), 10)",
            "$buy_lg_amount/($sell_lg_amount+1e-12)",
            "Mean($buy_lg_amount/($sell_lg_amount+1e-12), 5)",
            "$buy_elg_amount/($sell_elg_amount+1e-12)",
            "Mean($buy_elg_amount/($sell_elg_amount+1e-12), 5)",
            "$buy_sm_amount/($sell_sm_amount+1e-12)",
            "Mean($buy_sm_amount/($sell_sm_amount+1e-12), 5)",
        ]
        names += [
            "MFNET_AMT0",
            "MFNET_AMT_MA5",
            "MFNET_AMT_MA10",
            "MFNET_AMT_MA20",
            "MFNET_VOL0",
            "MFNET_VOL_MA5",
            "MFNET_VOL_MA10",
            "MFLG_NET",
            "MFLG_NET_MA5",
            "MFLG_NET_MA10",
            "MFLG_NET_MA20",
            "MFSM_NET",
            "MFSM_NET_MA5",
            "MFSM_NET_MA10",
            "MFMD_NET",
            "MFMD_NET_MA5",
            "MFMD_NET_MA10",
            "MFELG_NET",
            "MFELG_NET_MA5",
            "MFELG_NET_MA10",
            "MFLG_RATIO",
            "MFLG_RATIO_MA5",
            "MFLG_RATIO_MA10",
            "MF_SM_LG",
            "MF_SM_LG_MA5",
            "MFNET_MOM5",
            "MFNET_MOM10",
            "MFNET_MOM20",
            "MF_CORR5",
            "MF_CORR10",
            "MFLG_BUY_SELL",
            "MFLG_BUY_SELL_MA5",
            "MFELG_BUY_SELL",
            "MFELG_BUY_SELL_MA5",
            "MFSM_BUY_SELL",
            "MFSM_BUY_SELL_MA5",
        ]
        
class MarketCapCSRankNorm(Processor):
    """只对市值相关特征做截面排名标准化"""
    MARKET_CAP_COLS = ["TOTALMV"]
    def __call__(self, df):
        from qlib.data.dataset.processor import get_group_columns
        cols = get_group_columns(df, "feature")
        target_cols = [c for c in cols if c.get_level_values(-1)[0] in self.MARKET_CAP_COLS]
        if len(target_cols) > 0:
            ranked = df[target_cols].groupby("datetime", group_keys=False).rank(pct=True)
            ranked = (ranked - 0.5) * 3.46  # 标准化到均值0、标准差约1
            df[target_cols] = ranked
        return df
