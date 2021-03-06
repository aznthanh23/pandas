import os
import pytest

import numpy as np
from pandas.compat import zip

from pandas import (Series, Index, isnull,
                    to_datetime, DatetimeIndex, Timestamp,
                    Interval, IntervalIndex, Categorical,
                    cut, qcut, date_range)
import pandas.util.testing as tm

from pandas.core.algorithms import quantile
import pandas.core.reshape.tile as tmod


class TestCut(tm.TestCase):

    def test_simple(self):
        data = np.ones(5, dtype='int64')
        result = cut(data, 4, labels=False)
        expected = np.array([1, 1, 1, 1, 1])
        tm.assert_numpy_array_equal(result, expected,
                                    check_dtype=False)

    def test_bins(self):
        data = np.array([.2, 1.4, 2.5, 6.2, 9.7, 2.1])
        result, bins = cut(data, 3, retbins=True)

        intervals = IntervalIndex.from_breaks(bins.round(3))
        expected = intervals.take([0, 0, 0, 1, 2, 0]).astype('category')
        tm.assert_categorical_equal(result, expected)
        tm.assert_almost_equal(bins, np.array([0.1905, 3.36666667,
                                               6.53333333, 9.7]))

    def test_right(self):
        data = np.array([.2, 1.4, 2.5, 6.2, 9.7, 2.1, 2.575])
        result, bins = cut(data, 4, right=True, retbins=True)
        intervals = IntervalIndex.from_breaks(bins.round(3))
        expected = intervals.astype('category').take([0, 0, 0, 2, 3, 0, 0])
        tm.assert_categorical_equal(result, expected)
        tm.assert_almost_equal(bins, np.array([0.1905, 2.575, 4.95,
                                               7.325, 9.7]))

    def test_noright(self):
        data = np.array([.2, 1.4, 2.5, 6.2, 9.7, 2.1, 2.575])
        result, bins = cut(data, 4, right=False, retbins=True)
        intervals = IntervalIndex.from_breaks(bins.round(3), closed='left')
        expected = intervals.take([0, 0, 0, 2, 3, 0, 1]).astype('category')
        tm.assert_categorical_equal(result, expected)
        tm.assert_almost_equal(bins, np.array([0.2, 2.575, 4.95,
                                               7.325, 9.7095]))

    def test_arraylike(self):
        data = [.2, 1.4, 2.5, 6.2, 9.7, 2.1]
        result, bins = cut(data, 3, retbins=True)
        intervals = IntervalIndex.from_breaks(bins.round(3))
        expected = intervals.take([0, 0, 0, 1, 2, 0]).astype('category')
        tm.assert_categorical_equal(result, expected)
        tm.assert_almost_equal(bins, np.array([0.1905, 3.36666667,
                                               6.53333333, 9.7]))

    def test_bins_from_intervalindex(self):
        c = cut(range(5), 3)
        expected = c
        result = cut(range(5), bins=expected.categories)
        tm.assert_categorical_equal(result, expected)

        expected = Categorical.from_codes(np.append(c.codes, -1),
                                          categories=c.categories,
                                          ordered=True)
        result = cut(range(6), bins=expected.categories)
        tm.assert_categorical_equal(result, expected)

        # doc example
        # make sure we preserve the bins
        ages = np.array([10, 15, 13, 12, 23, 25, 28, 59, 60])
        c = cut(ages, bins=[0, 18, 35, 70])
        expected = IntervalIndex.from_tuples([(0, 18), (18, 35), (35, 70)])
        tm.assert_index_equal(c.categories, expected)

        result = cut([25, 20, 50], bins=c.categories)
        tm.assert_index_equal(result.categories, expected)
        tm.assert_numpy_array_equal(result.codes,
                                    np.array([1, 1, 2], dtype='int8'))

    def test_bins_not_monotonic(self):
        data = [.2, 1.4, 2.5, 6.2, 9.7, 2.1]
        pytest.raises(ValueError, cut, data, [0.1, 1.5, 1, 10])

    def test_wrong_num_labels(self):
        data = [.2, 1.4, 2.5, 6.2, 9.7, 2.1]
        pytest.raises(ValueError, cut, data, [0, 1, 10],
                      labels=['foo', 'bar', 'baz'])

    def test_cut_corner(self):
        # h3h
        pytest.raises(ValueError, cut, [], 2)

        pytest.raises(ValueError, cut, [1, 2, 3], 0.5)

    def test_cut_out_of_range_more(self):
        # #1511
        s = Series([0, -1, 0, 1, -3], name='x')
        ind = cut(s, [0, 1], labels=False)
        exp = Series([np.nan, np.nan, np.nan, 0, np.nan], name='x')
        tm.assert_series_equal(ind, exp)

    def test_labels(self):
        arr = np.tile(np.arange(0, 1.01, 0.1), 4)

        result, bins = cut(arr, 4, retbins=True)
        ex_levels = IntervalIndex.from_breaks([-1e-3, 0.25, 0.5, 0.75, 1])
        tm.assert_index_equal(result.categories, ex_levels)

        result, bins = cut(arr, 4, retbins=True, right=False)
        ex_levels = IntervalIndex.from_breaks([0, 0.25, 0.5, 0.75, 1 + 1e-3],
                                              closed='left')
        tm.assert_index_equal(result.categories, ex_levels)

    def test_cut_pass_series_name_to_factor(self):
        s = Series(np.random.randn(100), name='foo')

        factor = cut(s, 4)
        self.assertEqual(factor.name, 'foo')

    def test_label_precision(self):
        arr = np.arange(0, 0.73, 0.01)

        result = cut(arr, 4, precision=2)
        ex_levels = IntervalIndex.from_breaks([-0.00072, 0.18, 0.36,
                                               0.54, 0.72])
        tm.assert_index_equal(result.categories, ex_levels)

    def test_na_handling(self):
        arr = np.arange(0, 0.75, 0.01)
        arr[::3] = np.nan

        result = cut(arr, 4)

        result_arr = np.asarray(result)

        ex_arr = np.where(isnull(arr), np.nan, result_arr)

        tm.assert_almost_equal(result_arr, ex_arr)

        result = cut(arr, 4, labels=False)
        ex_result = np.where(isnull(arr), np.nan, result)
        tm.assert_almost_equal(result, ex_result)

    def test_inf_handling(self):
        data = np.arange(6)
        data_ser = Series(data, dtype='int64')

        bins = [-np.inf, 2, 4, np.inf]
        result = cut(data, bins)
        result_ser = cut(data_ser, bins)

        ex_uniques = IntervalIndex.from_breaks(bins)
        tm.assert_index_equal(result.categories, ex_uniques)
        self.assertEqual(result[5], Interval(4, np.inf))
        self.assertEqual(result[0], Interval(-np.inf, 2))
        self.assertEqual(result_ser[5], Interval(4, np.inf))
        self.assertEqual(result_ser[0], Interval(-np.inf, 2))

    def test_qcut(self):
        arr = np.random.randn(1000)

        # we store the bins as Index that have been rounded
        # to comparisions are a bit tricky
        labels, bins = qcut(arr, 4, retbins=True)
        ex_bins = quantile(arr, [0, .25, .5, .75, 1.])
        result = labels.categories.left.values
        self.assertTrue(np.allclose(result, ex_bins[:-1], atol=1e-2))
        result = labels.categories.right.values
        self.assertTrue(np.allclose(result, ex_bins[1:], atol=1e-2))

        ex_levels = cut(arr, ex_bins, include_lowest=True)
        tm.assert_categorical_equal(labels, ex_levels)

    def test_qcut_bounds(self):
        arr = np.random.randn(1000)

        factor = qcut(arr, 10, labels=False)
        self.assertEqual(len(np.unique(factor)), 10)

    def test_qcut_specify_quantiles(self):
        arr = np.random.randn(100)

        factor = qcut(arr, [0, .25, .5, .75, 1.])
        expected = qcut(arr, 4)
        tm.assert_categorical_equal(factor, expected)

    def test_qcut_all_bins_same(self):
        tm.assertRaisesRegexp(ValueError, "edges.*unique", qcut,
                              [0, 0, 0, 0, 0, 0, 0, 0, 0, 0], 3)

    def test_cut_out_of_bounds(self):
        arr = np.random.randn(100)

        result = cut(arr, [-1, 0, 1])

        mask = isnull(result)
        ex_mask = (arr < -1) | (arr > 1)
        tm.assert_numpy_array_equal(mask, ex_mask)

    def test_cut_pass_labels(self):
        arr = [50, 5, 10, 15, 20, 30, 70]
        bins = [0, 25, 50, 100]
        labels = ['Small', 'Medium', 'Large']

        result = cut(arr, bins, labels=labels)
        exp = Categorical(['Medium'] + 4 * ['Small'] + ['Medium', 'Large'],
                          ordered=True)
        tm.assert_categorical_equal(result, exp)

        result = cut(arr, bins, labels=Categorical.from_codes([0, 1, 2],
                                                              labels))
        exp = Categorical.from_codes([1] + 4 * [0] + [1, 2], labels)
        tm.assert_categorical_equal(result, exp)

    def test_qcut_include_lowest(self):
        values = np.arange(10)

        ii = qcut(values, 4)

        ex_levels = IntervalIndex.from_intervals(
            [Interval(-0.001, 2.25),
             Interval(2.25, 4.5),
             Interval(4.5, 6.75),
             Interval(6.75, 9)])
        tm.assert_index_equal(ii.categories, ex_levels)

    def test_qcut_nas(self):
        arr = np.random.randn(100)
        arr[:20] = np.nan

        result = qcut(arr, 4)
        self.assertTrue(isnull(result[:20]).all())

    def test_qcut_index(self):
        result = qcut([0, 2], 2)
        expected = Index([Interval(-0.001, 1), Interval(1, 2)]).astype(
            'category')
        tm.assert_categorical_equal(result, expected)

    def test_round_frac(self):
        # it works
        result = cut(np.arange(11.), 2)

        result = cut(np.arange(11.) / 1e10, 2)

        # #1979, negative numbers

        result = tmod._round_frac(-117.9998, precision=3)
        self.assertEqual(result, -118)
        result = tmod._round_frac(117.9998, precision=3)
        self.assertEqual(result, 118)

        result = tmod._round_frac(117.9998, precision=2)
        self.assertEqual(result, 118)
        result = tmod._round_frac(0.000123456, precision=2)
        self.assertEqual(result, 0.00012)

    def test_qcut_binning_issues(self):
        # #1978, 1979
        path = os.path.join(tm.get_data_path(), 'cut_data.csv')
        arr = np.loadtxt(path)

        result = qcut(arr, 20)

        starts = []
        ends = []
        for lev in np.unique(result):
            s = lev.left
            e = lev.right
            self.assertTrue(s != e)

            starts.append(float(s))
            ends.append(float(e))

        for (sp, sn), (ep, en) in zip(zip(starts[:-1], starts[1:]),
                                      zip(ends[:-1], ends[1:])):
            self.assertTrue(sp < sn)
            self.assertTrue(ep < en)
            self.assertTrue(ep <= sn)

    def test_cut_return_intervals(self):
        s = Series([0, 1, 2, 3, 4, 5, 6, 7, 8])
        res = cut(s, 3)
        exp_bins = np.linspace(0, 8, num=4).round(3)
        exp_bins[0] -= 0.008
        exp = Series(IntervalIndex.from_breaks(exp_bins, closed='right').take(
            [0, 0, 0, 1, 1, 1, 2, 2, 2])).astype('category', ordered=True)
        tm.assert_series_equal(res, exp)

    def test_qcut_return_intervals(self):
        s = Series([0, 1, 2, 3, 4, 5, 6, 7, 8])
        res = qcut(s, [0, 0.333, 0.666, 1])
        exp_levels = np.array([Interval(-0.001, 2.664),
                               Interval(2.664, 5.328), Interval(5.328, 8)])
        exp = Series(exp_levels.take([0, 0, 0, 1, 1, 1, 2, 2, 2])).astype(
            'category', ordered=True)
        tm.assert_series_equal(res, exp)

    def test_series_retbins(self):
        # GH 8589
        s = Series(np.arange(4))
        result, bins = cut(s, 2, retbins=True)
        expected = Series(IntervalIndex.from_breaks(
            [-0.003, 1.5, 3], closed='right').repeat(2)).astype('category',
                                                                ordered=True)
        tm.assert_series_equal(result, expected)

        result, bins = qcut(s, 2, retbins=True)
        expected = Series(IntervalIndex.from_breaks(
            [-0.001, 1.5, 3], closed='right').repeat(2)).astype('category',
                                                                ordered=True)
        tm.assert_series_equal(result, expected)

    def test_qcut_duplicates_bin(self):
        # GH 7751
        values = [0, 0, 0, 0, 1, 2, 3]
        expected = IntervalIndex.from_intervals([Interval(-0.001, 1),
                                                 Interval(1, 3)])

        result = qcut(values, 3, duplicates='drop')
        tm.assert_index_equal(result.categories, expected)

        pytest.raises(ValueError, qcut, values, 3)
        pytest.raises(ValueError, qcut, values, 3, duplicates='raise')

        # invalid
        pytest.raises(ValueError, qcut, values, 3, duplicates='foo')

    def test_single_quantile(self):
        # issue 15431
        expected = Series([0, 0])

        s = Series([9., 9.])
        result = qcut(s, 1, labels=False)
        tm.assert_series_equal(result, expected)
        result = qcut(s, 1)
        intervals = IntervalIndex([Interval(8.999, 9.0),
                                   Interval(8.999, 9.0)], closed='right')
        expected = Series(intervals).astype('category', ordered=True)
        tm.assert_series_equal(result, expected)

        s = Series([-9., -9.])
        expected = Series([0, 0])
        result = qcut(s, 1, labels=False)
        tm.assert_series_equal(result, expected)
        result = qcut(s, 1)
        intervals = IntervalIndex([Interval(-9.001, -9.0),
                                   Interval(-9.001, -9.0)], closed='right')
        expected = Series(intervals).astype('category', ordered=True)
        tm.assert_series_equal(result, expected)

        s = Series([0., 0.])
        expected = Series([0, 0])
        result = qcut(s, 1, labels=False)
        tm.assert_series_equal(result, expected)
        result = qcut(s, 1)
        intervals = IntervalIndex([Interval(-0.001, 0.0),
                                   Interval(-0.001, 0.0)], closed='right')
        expected = Series(intervals).astype('category', ordered=True)
        tm.assert_series_equal(result, expected)

        s = Series([9])
        expected = Series([0])
        result = qcut(s, 1, labels=False)
        tm.assert_series_equal(result, expected)
        result = qcut(s, 1)
        intervals = IntervalIndex([Interval(8.999, 9.0)], closed='right')
        expected = Series(intervals).astype('category', ordered=True)
        tm.assert_series_equal(result, expected)

        s = Series([-9])
        expected = Series([0])
        result = qcut(s, 1, labels=False)
        tm.assert_series_equal(result, expected)
        result = qcut(s, 1)
        intervals = IntervalIndex([Interval(-9.001, -9.0)], closed='right')
        expected = Series(intervals).astype('category', ordered=True)
        tm.assert_series_equal(result, expected)

        s = Series([0])
        expected = Series([0])
        result = qcut(s, 1, labels=False)
        tm.assert_series_equal(result, expected)
        result = qcut(s, 1)
        intervals = IntervalIndex([Interval(-0.001, 0.0)], closed='right')
        expected = Series(intervals).astype('category', ordered=True)
        tm.assert_series_equal(result, expected)

    def test_single_bin(self):
        # issue 14652
        expected = Series([0, 0])

        s = Series([9., 9.])
        result = cut(s, 1, labels=False)
        tm.assert_series_equal(result, expected)

        s = Series([-9., -9.])
        result = cut(s, 1, labels=False)
        tm.assert_series_equal(result, expected)

        expected = Series([0])

        s = Series([9])
        result = cut(s, 1, labels=False)
        tm.assert_series_equal(result, expected)

        s = Series([-9])
        result = cut(s, 1, labels=False)
        tm.assert_series_equal(result, expected)

        # issue 15428
        expected = Series([0, 0])

        s = Series([0., 0.])
        result = cut(s, 1, labels=False)
        tm.assert_series_equal(result, expected)

        expected = Series([0])

        s = Series([0])
        result = cut(s, 1, labels=False)
        tm.assert_series_equal(result, expected)

    def test_datetime_cut(self):
        # GH 14714
        # testing for time data to be present as series
        data = to_datetime(Series(['2013-01-01', '2013-01-02', '2013-01-03']))

        result, bins = cut(data, 3, retbins=True)
        expected = (
            Series(IntervalIndex.from_intervals([
                Interval(Timestamp('2012-12-31 23:57:07.200000'),
                         Timestamp('2013-01-01 16:00:00')),
                Interval(Timestamp('2013-01-01 16:00:00'),
                         Timestamp('2013-01-02 08:00:00')),
                Interval(Timestamp('2013-01-02 08:00:00'),
                         Timestamp('2013-01-03 00:00:00'))]))
            .astype('category', ordered=True))

        tm.assert_series_equal(result, expected)

        # testing for time data to be present as list
        data = [np.datetime64('2013-01-01'), np.datetime64('2013-01-02'),
                np.datetime64('2013-01-03')]
        result, bins = cut(data, 3, retbins=True)
        tm.assert_series_equal(Series(result), expected)

        # testing for time data to be present as ndarray
        data = np.array([np.datetime64('2013-01-01'),
                         np.datetime64('2013-01-02'),
                         np.datetime64('2013-01-03')])
        result, bins = cut(data, 3, retbins=True)
        tm.assert_series_equal(Series(result), expected)

        # testing for time data to be present as datetime index
        data = DatetimeIndex(['2013-01-01', '2013-01-02', '2013-01-03'])
        result, bins = cut(data, 3, retbins=True)
        tm.assert_series_equal(Series(result), expected)

    def test_datetime_bin(self):
        data = [np.datetime64('2012-12-13'), np.datetime64('2012-12-15')]
        bin_data = ['2012-12-12', '2012-12-14', '2012-12-16']
        expected = (
            Series(IntervalIndex.from_intervals([
                Interval(Timestamp(bin_data[0]), Timestamp(bin_data[1])),
                Interval(Timestamp(bin_data[1]), Timestamp(bin_data[2]))]))
            .astype('category', ordered=True))

        for conv in [Timestamp, Timestamp, np.datetime64]:
            bins = [conv(v) for v in bin_data]
            result = cut(data, bins=bins)
            tm.assert_series_equal(Series(result), expected)

        bin_pydatetime = [Timestamp(v).to_pydatetime() for v in bin_data]
        result = cut(data, bins=bin_pydatetime)
        tm.assert_series_equal(Series(result), expected)

        bins = to_datetime(bin_data)
        result = cut(data, bins=bin_pydatetime)
        tm.assert_series_equal(Series(result), expected)

    def test_datetime_nan(self):

        def f():
            cut(date_range('20130101', periods=3), bins=[0, 2, 4])
        pytest.raises(ValueError, f)

        result = cut(date_range('20130102', periods=5),
                     bins=date_range('20130101', periods=2))
        mask = result.categories.isnull()
        tm.assert_numpy_array_equal(mask, np.array([False]))
        mask = result.isnull()
        tm.assert_numpy_array_equal(
            mask, np.array([False, True, True, True, True]))


def curpath():
    pth, _ = os.path.split(os.path.abspath(__file__))
    return pth
