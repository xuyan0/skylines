import Ember from 'ember';

export default Ember.Component.extend({
  classNames: ['input-group', 'input-group-sm', 'date'],

  date: null,
  minDate: false,
  maxDate: false,
  onChange: Ember.K,

  didInsertElement() {
    this.$().datetimepicker({
      pickDate: false,
      useSeconds: true,
      format: 'HH:mm:ss',
      icons: {
        time: 'icon-time',
        date: 'icon-calendar',
        up: 'icon-chevron-up',
        down: 'icon-chevron-down',
      },
      minDate: this.get('minDate'),
      maxDate: this.get('maxDate'),
    });

    this.$().on('dp.change', ({ date }) => {
      this.get('onChange')(date.toDate());
    });

    this.set('picker', this.$().data('DateTimePicker'));

    Ember.run.once(this, 'updateDate');
  },

  didUpdateAttrs() {
    Ember.run.once(this, 'updateDate');
  },

  willDestroyElement() {
    this.$().off('dp.change');
    this.set('picker', null);
  },

  updateDate() {
    this.get('picker').setValue(this.get('date'));
  },
});
